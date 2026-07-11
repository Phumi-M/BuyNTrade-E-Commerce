from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone


class User(AbstractUser):
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)

    def seller_rating_stats(self):
        return self.seller_reviews.aggregate(
            average=Avg("rating"),
            count=Count("id"),
        )

    def seller_rating_display(self):
        stats = self.seller_rating_stats()
        if not stats["count"]:
            return "No ratings yet"
        return f"{stats['average']:.1f} / 5 ({stats['count']} review{'s' if stats['count'] != 1 else ''})"

    def get_profile_photo_url(self):
        if self.profile_photo:
            return self.profile_photo.url
        return None

    @property
    def profile_initial(self):
        return self.username[0].upper() if self.username else "?"



class Category(models.Model):
    name = models.CharField(max_length=64)

    def __str__(self):
        return f"{self.name}"


class Listing(models.Model):
    title = models.CharField(max_length=64)
    description = models.TextField()
    starting_bid = models.IntegerField()
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to="listings/images/", blank=True, null=True)
    video = models.FileField(upload_to="listings/videos/", blank=True, null=True)
    video_thumbnail = models.ImageField(upload_to="listings/thumbnails/", blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="listings")
    brand = models.CharField(max_length=64, blank=True, help_text="Product brand or manufacturer")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    area = models.CharField(max_length=64, blank=True, help_text="City or suburb for local buy/trade")
    active = models.BooleanField(default=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    watchlist = models.ManyToManyField(User, blank=True, related_name="watchlist")
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="won_listings")

    def __str__(self):
        return f"{self.id}: {self.title} (${self.starting_bid})"

    def get_display_image_url(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("gallery_images")
        if prefetched:
            return prefetched[0].image.url
        first_gallery = self.gallery_images.order_by("order", "id").first()
        if first_gallery:
            return first_gallery.image.url
        if self.image:
            return self.image.url
        if self.video_thumbnail:
            return self.video_thumbnail.url
        return self.image_url or None

    @property
    def has_video(self):
        return bool(self.video)

    def close_auction(self):
        if not self.active:
            return
        self.active = False
        highest_bid = self.bids.order_by("-amount").first()
        self.winner = highest_bid.bidder if highest_bid else None
        self.save(update_fields=["active", "winner"])

    def close_if_expired(self):
        if self.active and self.ends_at and timezone.now() >= self.ends_at:
            self.close_auction()
            return True
        return False

    @property
    def is_expired(self):
        return bool(self.ends_at and timezone.now() >= self.ends_at)

    @property
    def time_left_label(self):
        if not self.active:
            return "Closed"
        if not self.ends_at:
            return "Live"
        if self.is_expired:
            return "Closed"
        delta = self.ends_at - timezone.now()
        days = delta.days
        hours = delta.seconds // 3600
        if days >= 1:
            return f"{days}d left"
        if hours >= 1:
            return f"{hours}h left"
        minutes = max((delta.seconds % 3600) // 60, 1)
        return f"{minutes}m left"

    @classmethod
    def close_expired(cls):
        now = timezone.now()
        expired = cls.objects.filter(active=True, ends_at__lte=now)
        for listing in expired:
            listing.close_auction()


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="listings/gallery/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image {self.id} for {self.listing.title}"


class Bid(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="bids")
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bids")
    amount = models.IntegerField()

    def __str__(self):
        return f"Bid {self.id}: {self.amount} by {self.bidder.username}"


class Comment(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="comments")
    commenter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment {self.id} on {self.listing.title}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="messages")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.username} to {self.receiver.username}"


class SellerReview(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="seller_reviews")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_given")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="seller_reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reviewer", "listing"], name="unique_review_per_listing"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}/5 for {self.seller.username} by {self.reviewer.username}"


class ListingViewHistory(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="listing_views",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="view_records")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at"]

    def __str__(self):
        viewer = self.user.username if self.user_id else self.session_key[:8]
        return f"{viewer} viewed {self.listing.title}"


class CommunityPost(models.Model):
    author_name = models.CharField(max_length=64)
    role = models.CharField(max_length=64)
    text = models.TextField()
    likes = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="community_posts",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author_name}: {self.text[:40]}"

    @property
    def initial(self):
        return self.author_name[0].upper() if self.author_name else "?"

    def time_label(self):
        from django.utils import timezone

        elapsed = timezone.now() - self.created_at
        hours = int(elapsed.total_seconds() // 3600)
        if hours < 1:
            return "Just now"
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days == 1:
            return "1d ago"
        return f"{days}d ago"
