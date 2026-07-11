from django.contrib import admin
from .models import Listing, Category, Bid, Comment, CommunityPost, SellerReview, Message, ListingImage


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    inlines = [ListingImageInline]


admin.site.site_header = "BuyNTrade E-commerce Administration"
admin.site.site_title = "BuyNTrade E-commerce"
admin.site.index_title = "Site Administration"
admin.site.register(Category)
admin.site.register(Bid)
admin.site.register(Comment)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "listing", "created_at")
    list_filter = ("created_at",)
    search_fields = ("sender__username", "receiver__username", "listing__title", "text")


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ("seller", "reviewer", "listing", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ("author_name", "role", "likes", "is_featured", "is_published", "created_at")
    list_filter = ("is_featured", "is_published")
    search_fields = ("author_name", "role", "text")
