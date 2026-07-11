from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from datetime import timedelta

from .models import User, Listing, Category, Bid, Comment, CommunityPost, SellerReview, Message, ListingImage
from .recommendations import (
    get_recommended_listings,
    recommended_listing_cards,
    record_listing_view,
)


LISTINGS_PER_PAGE = 9


SIDEBAR_CATEGORIES = [
    "Electronics",
    "Appliances",
    "Fashion & Clothing",
    "Sports & Outdoors",
]

POPULAR_AREAS = [
    "Johannesburg",
    "Pretoria",
    "Sandton",
    "Brakpan",
    "Benoni",
    "Boksburg",
    "Springs",
    "East Rand",
    "Soweto",
    "Midrand",
]


def _sidebar_categories():
    categories = []
    for name in SIDEBAR_CATEGORIES:
        category = Category.objects.filter(name=name).first()
        if category:
            categories.append(category)
    return categories


def _sidebar_context(active_category_id=None, active_sidebar=None):
    return {
        "categories": _sidebar_categories(),
        "active_category_id": active_category_id,
        "active_sidebar": active_sidebar,
        "popular_areas": POPULAR_AREAS,
    }


class _BidAmount:
    def __init__(self, amount):
        self.amount = amount


def _highest_bid_from_listing(listing):
    if hasattr(listing, "top_bid") and listing.top_bid is not None:
        return _BidAmount(listing.top_bid)
    return listing.bids.order_by("-amount").first()


def _shop_listings_queryset(listings):
    return (
        listings.select_related("category", "owner")
        .prefetch_related("gallery_images")
        .annotate(top_bid=Max("bids__amount"))
    )


def _listing_cards(request, listings):
    watchlist_ids = set()
    if request.user.is_authenticated:
        watchlist_ids = set(request.user.watchlist.values_list("id", flat=True))

    listings_data = []
    for listing in listings:
        listings_data.append({
            "listing": listing,
            "highest_bid": _highest_bid_from_listing(listing),
        })

    return listings_data, watchlist_ids


def _listing_detail_context(request, listing, error=None):
    gallery_images = list(listing.gallery_images.all())
    highest_bid = listing.bids.select_related("bidder").order_by("-amount").first()
    context = {
        "listing": listing,
        "gallery_images": gallery_images,
        "bids": listing.bids.select_related("bidder").order_by("-amount"),
        "comments": listing.comments.select_related("commenter").order_by("-timestamp"),
        "highest_bid": highest_bid,
        "recommendations": recommended_listing_cards(
            get_recommended_listings(request, source_listing=listing)
        ),
        "is_owner": request.user.is_authenticated and request.user == listing.owner,
        "is_in_watchlist": (
            request.user.is_authenticated
            and listing.watchlist.filter(pk=request.user.pk).exists()
        ),
        "won_listing": (
            not listing.active
            and listing.winner
            and request.user.is_authenticated
            and request.user == listing.winner
        ),
        "watchlist_ids": (
            set(request.user.watchlist.values_list("id", flat=True))
            if request.user.is_authenticated
            else set()
        ),
    }
    if error:
        context["error"] = error
    return context


def _pagination_query(request, exclude=("page",)):
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def _paginate_listings(request, listings, per_page=LISTINGS_PER_PAGE):
    listings = _shop_listings_queryset(listings)
    paginator = Paginator(listings.order_by("-id"), per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    listings_data, watchlist_ids = _listing_cards(request, page_obj.object_list)
    return listings_data, watchlist_ids, page_obj


def _listings_max_price(listings):
    listing_ids = listings.values_list("id", flat=True)
    max_starting = listings.aggregate(max_price=Max("starting_bid"))["max_price"] or 0
    max_bid = 0
    if listing_ids:
        max_bid = Bid.objects.filter(listing_id__in=listing_ids).aggregate(
            max_price=Max("amount")
        )["max_price"] or 0
    return max(max_starting, max_bid, 500)


def _message_threads(user):
    messages = Message.objects.filter(
        Q(sender=user) | Q(receiver=user)
    ).select_related("sender", "receiver", "listing").order_by("-created_at")

    threads = {}
    for message in messages:
        other_user = message.receiver if message.sender_id == user.id else message.sender
        key = (message.listing_id, other_user.id)
        if key not in threads:
            threads[key] = {
                "listing": message.listing,
                "other_user": other_user,
                "latest_message": message,
            }
    return list(threads.values())


def _spotlight_posts(limit=2):
    featured = list(
        CommunityPost.objects.filter(is_published=True, is_featured=True).order_by("-created_at")[:limit]
    )
    if len(featured) >= limit:
        return featured

    featured_ids = [post.id for post in featured]
    remaining = limit - len(featured)
    recent = CommunityPost.objects.filter(is_published=True).exclude(id__in=featured_ids).order_by("-created_at")[:remaining]
    return featured + list(recent)


def _filter_listings_by_search(listings, query):
    if not query:
        return listings
    return listings.filter(
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(category__name__icontains=query)
    )


def _filter_listings_by_location(listings, location):
    if not location:
        return listings
    return listings.filter(area__icontains=location)


def _refresh_listings():
    Listing.close_expired()


def index(request):
    _refresh_listings()
    search_query = request.GET.get("q", "").strip()
    location_query = request.GET.get("location", "").strip()
    listings = Listing.objects.filter(active=True)
    listings = _filter_listings_by_search(listings, search_query)
    listings = _filter_listings_by_location(listings, location_query)
    listings_data, watchlist_ids, page_obj = _paginate_listings(request, listings)
    max_price = _listings_max_price(listings)
    recommendations = recommended_listing_cards(
        get_recommended_listings(request, source_listing=None)
    )

    return render(request, "buyntrade/index.html", {
        "listings_data": listings_data,
        "watchlist_ids": watchlist_ids,
        "page_obj": page_obj,
        "pagination_query": _pagination_query(request),
        "spotlight_posts": _spotlight_posts(),
        "max_price": max_price,
        "search_query": search_query,
        "location_query": location_query,
        "search_action": reverse("index"),
        "recommendations": recommendations,
        **_sidebar_context(active_sidebar="shop"),
    })


def _safe_next_url(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse("index")


def login_view(request):
    next_url = request.GET.get("next", "")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if not username or not password:
            return render(request, "buyntrade/login.html", {
                "message": "Please enter your username and password.",
                "next": request.POST.get("next", ""),
            })
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return HttpResponseRedirect(_safe_next_url(request, request.POST.get("next")))
        else:
            return render(request, "buyntrade/login.html", {
                "message": "Invalid username and/or password.",
                "next": request.POST.get("next", ""),
            })

    return render(request, "buyntrade/login.html", {
        "next": next_url,
    })


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")

        if not username or not email or not password:
            return render(request, "buyntrade/register.html", {
                "message": "All fields are required."
            })

        # Ensure password matches confirmation
        if password != confirmation:
            return render(request, "buyntrade/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "buyntrade/register.html", {
                "message": "Username already taken."
            })

        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "buyntrade/register.html")

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_VIDEO_SIZE = 10 * 1024 * 1024
MAX_GALLERY_IMAGES = 8
MAX_PROFILE_PHOTO_SIZE = 2 * 1024 * 1024


def _collect_uploaded_images(request):
    images = request.FILES.getlist("images")
    if images:
        return images
    single = request.FILES.get("image")
    return [single] if single else []


def _save_gallery_images(listing, image_files):
    if not image_files:
        return

    current_count = listing.gallery_images.count()
    available = MAX_GALLERY_IMAGES - current_count
    if available <= 0:
        return

    for index, image_file in enumerate(image_files[:available]):
        if image_file.size > MAX_IMAGE_SIZE:
            continue
        ListingImage.objects.create(
            listing=listing,
            image=image_file,
            order=current_count + index,
        )

    first = listing.gallery_images.order_by("order", "id").first()
    if first:
        listing.image = first.image
        listing.save(update_fields=["image"])


def _sync_primary_image(listing):
    first = listing.gallery_images.order_by("order", "id").first()
    listing.image = first.image if first else None
    listing.save(update_fields=["image"])


@login_required
def create_listing(request):
    categories = Category.objects.all()

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        image_url = request.POST.get("image_url", "").strip()
        category_id = request.POST.get("category")
        area = request.POST.get("area", "").strip()
        brand = request.POST.get("brand", "").strip()

        image_files = _collect_uploaded_images(request)
        video_file = request.FILES.get("video")
        thumbnail_file = request.FILES.get("video_thumbnail")

        errors = []
        if not title:
            errors.append("Title is required.")
        elif len(title) > 64:
            errors.append("Title must be 64 characters or fewer.")
        if not description:
            errors.append("Description is required.")
        try:
            starting_bid = int(float(request.POST.get("starting_bid", "")))
            if starting_bid < 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("Enter a valid starting bid.")
            starting_bid = 0
        try:
            duration_days = int(request.POST.get("duration_days", 7))
            if duration_days not in (3, 5, 7, 14):
                raise ValueError
        except (TypeError, ValueError):
            errors.append("Choose a valid auction duration.")
            duration_days = 7
        category = None
        if category_id:
            category = Category.objects.filter(pk=category_id).first()
            if not category:
                errors.append("Invalid category selected.")
        if not area:
            errors.append("Please enter your city or area.")
        for image_file in image_files:
            if image_file.size > MAX_IMAGE_SIZE:
                errors.append("Each photo must be under 5 MB.")
                break
        if len(image_files) > MAX_GALLERY_IMAGES:
            errors.append(f"You can upload up to {MAX_GALLERY_IMAGES} photos.")
        if video_file and video_file.size > MAX_VIDEO_SIZE:
            errors.append("Video must be under 10 MB.")

        if errors:
            return render(request, "buyntrade/create.html", {
                "categories": categories,
                "popular_areas": POPULAR_AREAS,
                "errors": errors,
                "form_data": request.POST,
                "active_sidebar": "sell",
            })

        listing = Listing(
            title=title,
            description=description,
            starting_bid=starting_bid,
            image_url=image_url or None,
            category=category,
            brand=brand,
            owner=request.user,
            area=area,
            ends_at=timezone.now() + timedelta(days=duration_days),
        )
        if video_file:
            listing.video = video_file
        if thumbnail_file:
            listing.video_thumbnail = thumbnail_file
        listing.save()
        _save_gallery_images(listing, image_files)

        return HttpResponseRedirect(reverse("index"))

    return render(request, "buyntrade/create.html", {
        "categories": categories,
        "popular_areas": POPULAR_AREAS,
        "active_sidebar": "sell",
    })


@login_required
def my_listings_view(request):
    _refresh_listings()
    listings = request.user.listings.select_related("category", "winner").order_by("-id")
    listing_rows = []
    for listing in listings:
        listing_rows.append({
            "listing": listing,
            "highest_bid": listing.bids.order_by("-amount").first(),
        })

    return render(request, "buyntrade/my_listings.html", {
        "active_sidebar": "my_listings",
        "listing_rows": listing_rows,
        **_sidebar_context(),
    })


@login_required
def edit_listing(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id, owner=request.user)
    if not listing.active:
        return redirect("my_listings")

    categories = Category.objects.all()
    highest_bid = listing.bids.order_by("-amount").first()
    can_edit_price = not listing.bids.exists()

    if request.method == "POST":
        title = request.POST["title"].strip()
        description = request.POST["description"].strip()
        area = request.POST.get("area", "").strip()
        brand = request.POST.get("brand", "").strip()
        category_id = request.POST.get("category")
        category = Category.objects.get(pk=category_id) if category_id else None
        image_files = _collect_uploaded_images(request)
        delete_image_ids = request.POST.getlist("delete_images")

        errors = []
        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if not area:
            errors.append("Please enter your city or area.")
        for image_file in image_files:
            if image_file.size > MAX_IMAGE_SIZE:
                errors.append("Each photo must be under 5 MB.")
                break
        valid_delete_count = listing.gallery_images.filter(id__in=delete_image_ids).count()
        remaining = listing.gallery_images.count() - valid_delete_count + len(image_files)
        if remaining > MAX_GALLERY_IMAGES:
            errors.append(f"A listing can have up to {MAX_GALLERY_IMAGES} photos.")

        if errors:
            return render(request, "buyntrade/edit.html", {
                "listing": listing,
                "gallery_images": listing.gallery_images.all(),
                "categories": categories,
                "popular_areas": POPULAR_AREAS,
                "highest_bid": highest_bid,
                "can_edit_price": can_edit_price,
                "errors": errors,
                "form_data": request.POST,
            })

        listing.title = title
        listing.description = description
        listing.area = area
        listing.brand = brand
        listing.category = category
        if can_edit_price:
            listing.starting_bid = int(float(request.POST["starting_bid"]))
        listing.save()

        if delete_image_ids:
            listing.gallery_images.filter(id__in=delete_image_ids).delete()
        _save_gallery_images(listing, image_files)
        _sync_primary_image(listing)

        return redirect("my_listings")

    return render(request, "buyntrade/edit.html", {
        "listing": listing,
        "gallery_images": listing.gallery_images.all(),
        "categories": categories,
        "popular_areas": POPULAR_AREAS,
        "highest_bid": highest_bid,
        "can_edit_price": can_edit_price,
    })


def listing_view(request, listing_id):
    _refresh_listings()
    listing = get_object_or_404(
        Listing.objects.select_related("category", "owner").prefetch_related("gallery_images"),
        pk=listing_id,
    )

    record_listing_view(request, listing)

    return render(request, "buyntrade/listing.html", _listing_detail_context(request, listing))


@login_required
def toggle_watchlist(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    if listing.watchlist.filter(pk=request.user.pk).exists():
        listing.watchlist.remove(request.user)
    else:
        listing.watchlist.add(request.user)
    return redirect('listing', listing_id=listing_id)

@login_required
def place_bid(request, listing_id):
    listing = get_object_or_404(
        Listing.objects.select_related("owner").prefetch_related("gallery_images"),
        pk=listing_id,
    )
    listing.close_if_expired()
    listing.refresh_from_db()

    if request.user == listing.owner:
        return render(
            request,
            "buyntrade/listing.html",
            _listing_detail_context(request, listing, error="You cannot bid on your own listing."),
        )

    if not listing.active:
        return render(
            request,
            "buyntrade/listing.html",
            _listing_detail_context(request, listing, error="This auction has ended."),
        )

    try:
        bid_amount = int(float(request.POST.get("bid_amount", "")))
    except (TypeError, ValueError):
        return render(
            request,
            "buyntrade/listing.html",
            _listing_detail_context(request, listing, error="Enter a valid bid amount."),
        )

    highest_bid = listing.bids.order_by("-amount").first()
    min_bid = listing.starting_bid
    if highest_bid:
        min_bid = highest_bid.amount + 1

    if bid_amount < min_bid:
        return render(
            request,
            "buyntrade/listing.html",
            _listing_detail_context(
                request,
                listing,
                error=f"Your bid must be at least R{min_bid},00.",
            ),
        )

    with transaction.atomic():
        locked = Listing.objects.select_for_update().get(pk=listing_id)
        locked.close_if_expired()
        highest_bid = locked.bids.order_by("-amount").first()
        min_bid = locked.starting_bid if not highest_bid else highest_bid.amount + 1
        if not locked.active or bid_amount < min_bid:
            listing = get_object_or_404(
                Listing.objects.select_related("category", "owner").prefetch_related("gallery_images"),
                pk=listing_id,
            )
            return render(
                request,
                "buyntrade/listing.html",
                _listing_detail_context(
                    request,
                    listing,
                    error="Someone else placed a higher bid. Try again.",
                ),
            )
        Bid(bidder=request.user, listing=locked, amount=bid_amount).save()

    return redirect("listing", listing_id=listing_id)


@login_required
def close_listing(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    if request.user != listing.owner:
        return redirect('listing', listing_id=listing_id)

    listing.close_auction()
    if request.POST.get("next") == "my_listings":
        return redirect("my_listings")
    return redirect('listing', listing_id=listing_id)

@login_required
def add_comment(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    content = request.POST.get("comment")
    if content:
        comment = Comment(commenter=request.user, listing=listing, text=content)
        comment.save()
    return redirect('listing', listing_id=listing_id)

def categories_view(request):
    categories = Category.objects.all()
    return render(request, "buyntrade/categories.html", {"categories": categories})


def seller_profile_view(request, username):
    seller = get_object_or_404(User, username=username)
    _refresh_listings()

    active_listings = seller.listings.filter(active=True)
    active_listings_count = active_listings.count()
    total_listings_count = seller.listings.count()
    listings_data, watchlist_ids, page_obj = _paginate_listings(request, active_listings)
    reviews = seller.seller_reviews.select_related("reviewer", "listing")
    rating_stats = seller.seller_rating_stats()
    completed_sales = seller.listings.filter(active=False, winner__isnull=False).count()

    reviewable_listings = Listing.objects.none()
    if request.user.is_authenticated and request.user != seller:
        reviewed_listing_ids = SellerReview.objects.filter(
            reviewer=request.user,
            seller=seller,
        ).values_list("listing_id", flat=True)
        reviewable_listings = Listing.objects.filter(
            owner=seller,
            winner=request.user,
            active=False,
        ).exclude(id__in=reviewed_listing_ids)

    return render(request, "buyntrade/seller_profile.html", {
        "seller": seller,
        "listings_data": listings_data,
        "watchlist_ids": watchlist_ids,
        "page_obj": page_obj,
        "pagination_query": _pagination_query(request),
        "active_listings_count": active_listings_count,
        "total_listings_count": total_listings_count,
        "reviews": reviews,
        "rating_stats": rating_stats,
        "completed_sales": completed_sales,
        "reviewable_listings": reviewable_listings,
        **_sidebar_context(),
    })


@login_required
def add_seller_review(request, username):
    if request.method != "POST":
        return redirect("seller_profile", username=username)

    seller = get_object_or_404(User, username=username)
    listing_id = request.POST.get("listing_id")
    try:
        rating = int(request.POST.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    comment = request.POST.get("comment", "").strip()

    listing = get_object_or_404(
        Listing,
        pk=listing_id,
        owner=seller,
        winner=request.user,
        active=False,
    )

    if rating < 1 or rating > 5:
        return redirect("seller_profile", username=username)

    SellerReview.objects.update_or_create(
        reviewer=request.user,
        listing=listing,
        defaults={
            "seller": seller,
            "rating": rating,
            "comment": comment,
        },
    )
    return redirect("seller_profile", username=username)


def category_listings_view(request, category_id):
    _refresh_listings()
    category = get_object_or_404(Category, pk=category_id)
    listings = category.listings.filter(active=True)
    search_query = request.GET.get("q", "").strip()
    location_query = request.GET.get("location", "").strip()
    listings = _filter_listings_by_search(listings, search_query)
    listings = _filter_listings_by_location(listings, location_query)
    listings_data, watchlist_ids, page_obj = _paginate_listings(request, listings)
    max_price = _listings_max_price(listings)
    return render(request, "buyntrade/category_listings.html", {
        "category": category,
        "listings_data": listings_data,
        "watchlist_ids": watchlist_ids,
        "page_obj": page_obj,
        "pagination_query": _pagination_query(request),
        "max_price": max_price,
        "search_query": search_query,
        "location_query": location_query,
        "search_action": reverse("category_listings", kwargs={"category_id": category.id}),
        **_sidebar_context(active_category_id=category.id, active_sidebar="shop"),
    })

@login_required
def watchlist_view(request):
    _refresh_listings()
    listings = request.user.watchlist.filter(active=True)
    listings_data, watchlist_ids, page_obj = _paginate_listings(request, listings)
    return render(request, "buyntrade/watchlist.html", {
        "listings_data": listings_data,
        "watchlist_ids": watchlist_ids,
        "page_obj": page_obj,
        "pagination_query": _pagination_query(request),
        **_sidebar_context(active_sidebar="favorites"),
    })


def community_view(request):
    posts = CommunityPost.objects.filter(is_published=True)
    return render(request, "buyntrade/community.html", {
        "community_posts": posts,
    })


@login_required
def like_community_post(request, post_id):
    if request.method != "POST":
        return redirect("community")

    post = get_object_or_404(CommunityPost, pk=post_id, is_published=True)
    session_key = f"liked_post_{post_id}"
    if not request.session.get(session_key):
        post.likes += 1
        post.save(update_fields=["likes"])
        request.session[session_key] = True
        request.session.modified = True

    next_url = request.POST.get("next") or reverse("community")
    return redirect(next_url)


def about_view(request):
    return render(request, "buyntrade/about.html")


def help_view(request):
    return render(request, "buyntrade/help.html")


def terms_view(request):
    return render(request, "buyntrade/terms.html")


@login_required
def dashboard_view(request):
    return render(request, "buyntrade/dashboard.html", {
        "active_sidebar": "dashboard",
        "active_listings_count": request.user.listings.filter(active=True).count(),
        "watchlist_count": request.user.watchlist.count(),
        "bids_count": request.user.bids.count(),
        "won_count": request.user.won_listings.count(),
        **_sidebar_context(),
    })


@login_required
def orders_view(request):
    return render(request, "buyntrade/orders.html", {
        "active_sidebar": "orders",
        "purchases": Listing.objects.filter(winner=request.user).order_by("-id"),
        **_sidebar_context(),
    })


@login_required
def messages_view(request):
    return render(request, "buyntrade/messages.html", {
        "active_sidebar": "messages",
        "message_threads": _message_threads(request.user),
        **_sidebar_context(),
    })


@login_required
def message_thread_view(request, listing_id, username):
    listing = get_object_or_404(Listing, pk=listing_id)
    other_user = get_object_or_404(User, username=username)

    if request.user == other_user:
        return redirect("messages")

    thread_messages = Message.objects.filter(
        listing=listing,
    ).filter(
        Q(sender=request.user, receiver=other_user)
        | Q(sender=other_user, receiver=request.user)
    ).select_related("sender", "receiver").order_by("created_at")

    if not thread_messages.exists():
        return redirect("messages")

    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        if text:
            Message.objects.create(
                sender=request.user,
                receiver=other_user,
                listing=listing,
                text=text,
            )
        return redirect("message_thread", listing_id=listing_id, username=username)

    return render(request, "buyntrade/message_thread.html", {
        "active_sidebar": "messages",
        "listing": listing,
        "other_user": other_user,
        "thread_messages": thread_messages,
        **_sidebar_context(),
    })


@login_required
def send_message(request, listing_id):
    if request.method != "POST":
        return redirect("listing", listing_id=listing_id)

    listing = get_object_or_404(Listing, pk=listing_id)
    text = request.POST.get("text", "").strip()

    if request.user == listing.owner or not text:
        return redirect("listing", listing_id=listing_id)

    Message.objects.create(
        sender=request.user,
        receiver=listing.owner,
        listing=listing,
        text=text,
    )
    return redirect("message_thread", listing_id=listing_id, username=listing.owner.username)


@login_required
def settings_view(request):
    errors = []

    if request.method == "POST":
        bio = request.POST.get("bio", "").strip()[:500]
        photo_file = request.FILES.get("profile_photo")
        remove_photo = request.POST.get("remove_photo") == "on"

        if photo_file and photo_file.size > MAX_PROFILE_PHOTO_SIZE:
            errors.append("Profile photo must be under 2 MB.")
        else:
            request.user.bio = bio
            if remove_photo and request.user.profile_photo:
                request.user.profile_photo.delete(save=False)
                request.user.profile_photo = None
            elif photo_file:
                if request.user.profile_photo:
                    request.user.profile_photo.delete(save=False)
                request.user.profile_photo = photo_file
            request.user.save()
            if not errors:
                return redirect("settings")

    return render(request, "buyntrade/settings.html", {
        "active_sidebar": "settings",
        "errors": errors,
        **_sidebar_context(),
    })