from django.db import models


class Album(models.Model):
    title = models.CharField(max_length=100)
    is_featured = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.title


class Image(models.Model):
    album = models.ForeignKey(Album, related_name="images", on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    is_primary = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.title


class AlbumStacked(Album):
    """Same table as Album, registered separately so the admin can show
    a StackedInline example next to Album's TabularInline one."""

    class Meta:
        proxy = True
        verbose_name = "Album (stacked inline demo)"
        verbose_name_plural = "Albums (stacked inline demo)"
