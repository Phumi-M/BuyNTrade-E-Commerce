from django.db.models import Max, Q
from django.utils import timezone

from .models import Listing, ListingViewHistory

RECOMMENDATIONS_LIMIT = 4
PRICE_TOLERANCE = 0.35
SESSION_HISTORY_KEY = "recently_viewed"
SESSION_HISTORY_MAX = 20
USER_HISTORY_MAX = 50


class _BidAmount:
    def __init__(self, amount):
        self.amount = amount


def _normalize_brand(brand):
    return brand.strip().lower() if brand else ""


def _effective_price(listing):
    if hasattr(listing, "top_bid") and listing.top_bid is not None:
        return listing.top_bid
    highest_bid = listing.bids.order_by("-amount").first()
    return highest_bid.amount if highest_bid else listing.starting_bid


def record_listing_view(request, listing):
    from datetime import timedelta

    user = request.user if request.user.is_authenticated else None
    dedupe_since = timezone.now() - timedelta(minutes=30)

    if user:
        if ListingViewHistory.objects.filter(
            user=user,
            listing=listing,
            viewed_at__gte=dedupe_since,
        ).exists():
            return
        ListingViewHistory.objects.create(user=user, listing=listing)
        stale_ids = list(
            ListingViewHistory.objects.filter(user=user)
            .order_by("-viewed_at")
            .values_list("id", flat=True)[USER_HISTORY_MAX:]
        )
        if stale_ids:
            ListingViewHistory.objects.filter(id__in=stale_ids).delete()
        return

    if not request.session.session_key:
        request.session.create()

    recent = request.session.get(SESSION_HISTORY_KEY, [])
    listing_id = listing.id
    if listing_id in recent:
        recent.remove(listing_id)
    recent.insert(0, listing_id)
    request.session[SESSION_HISTORY_KEY] = recent[:SESSION_HISTORY_MAX]
    request.session.modified = True

    session_key = request.session.session_key or ""
    ListingViewHistory.objects.create(
        session_key=session_key,
        listing=listing,
    )


def _distinct_history_ids(request, user, exclude_id=None, limit=10):
    ids = []

    if user:
        seen = set()
        for listing_id in ListingViewHistory.objects.filter(user=user).values_list(
            "listing_id", flat=True
        ):
            if listing_id in seen:
                continue
            seen.add(listing_id)
            ids.append(listing_id)
            if len(ids) >= limit:
                break
    else:
        ids = list(request.session.get(SESSION_HISTORY_KEY, []))[:limit]

    if exclude_id:
        ids = [listing_id for listing_id in ids if listing_id != exclude_id]
    return ids


def _history_listings(request, user, exclude_id=None):
    history_ids = _distinct_history_ids(request, user, exclude_id=exclude_id)
    if not history_ids:
        return []

    listings = {
        listing.id: listing
        for listing in Listing.objects.filter(id__in=history_ids, active=True).select_related(
            "category"
        )
    }
    return [listings[listing_id] for listing_id in history_ids if listing_id in listings]


def _active_candidates(exclude_ids):
    return (
        Listing.objects.filter(active=True)
        .exclude(id__in=exclude_ids)
        .select_related("category", "owner")
        .prefetch_related("gallery_images")
        .annotate(top_bid=Max("bids__amount"))
    )


def get_recommended_listings(request, source_listing=None, limit=RECOMMENDATIONS_LIMIT):
    user = request.user if request.user.is_authenticated else None
    history_listings = _history_listings(
        request,
        user,
        exclude_id=source_listing.pk if source_listing else None,
    )
    history_ids = {listing.id for listing in history_listings}
    history_categories = {listing.category_id for listing in history_listings if listing.category_id}
    history_brands = {_normalize_brand(listing.brand) for listing in history_listings if listing.brand}

    exclude_ids = set(history_ids)
    if source_listing:
        exclude_ids.add(source_listing.pk)

    if source_listing:
        base_price = _effective_price(source_listing)
        price_min = int(base_price * (1 - PRICE_TOLERANCE))
        price_max = int(base_price * (1 + PRICE_TOLERANCE))
        source_category_id = source_listing.category_id
        source_brand = _normalize_brand(source_listing.brand)
    else:
        price_min = price_max = None
        source_category_id = None
        source_brand = ""

    if not source_listing and not history_listings:
        return []

    scored = []
    candidates = _active_candidates(exclude_ids)
    if source_listing and source_category_id:
        candidates = candidates.filter(
            Q(category_id=source_category_id)
            | Q(brand__iexact=source_listing.brand)
        ) if source_listing.brand else candidates.filter(category_id=source_category_id)
    elif history_categories:
        candidates = candidates.filter(category_id__in=history_categories)

    for candidate in candidates[:60]:
        score = 0
        candidate_price = _effective_price(candidate)
        candidate_brand = _normalize_brand(candidate.brand)

        if source_listing:
            if source_category_id and candidate.category_id == source_category_id:
                score += 40
            if source_brand and candidate_brand == source_brand:
                score += 30
            if price_min <= candidate_price <= price_max:
                score += 25
            elif price_min * 0.7 <= candidate_price <= price_max * 1.3:
                score += 10

        if candidate.category_id in history_categories:
            score += 20 if not source_listing else 8
        if candidate_brand and candidate_brand in history_brands:
            score += 15 if not source_listing else 12

        for viewed in history_listings:
            if viewed.category_id and candidate.category_id == viewed.category_id:
                score += 6
            viewed_brand = _normalize_brand(viewed.brand)
            if viewed_brand and candidate_brand == viewed_brand:
                score += 8

        if score > 0:
            scored.append((score, candidate.id, candidate))

    scored.sort(key=lambda row: (-row[0], -row[1]))
    results = [candidate for _, _, candidate in scored[:limit]]

    if len(results) < limit and source_listing and source_category_id:
        for candidate in _active_candidates(exclude_ids).filter(category_id=source_category_id):
            if candidate not in results:
                results.append(candidate)
            if len(results) >= limit:
                break

    return results[:limit]


def recommended_listing_cards(listings):
    cards = []
    for listing in listings:
        if hasattr(listing, "top_bid") and listing.top_bid is not None:
            highest_bid = _BidAmount(listing.top_bid)
        else:
            highest_bid = listing.bids.order_by("-amount").first()
        cards.append({"listing": listing, "highest_bid": highest_bid})
    return cards
