"""
Custom Storage Backend for S3

Uses django-storages with boto3 for S3 file storage.
"""

from storages.backends.s3boto3 import S3Boto3Storage


class GuidelineStorage(S3Boto3Storage):
    """
    S3 storage for guideline files.

    Files are stored in the 'guidelines/' folder in the S3 bucket.
    """
    location = 'guidelines'
    file_overwrite = False  # Don't overwrite files with same name
    default_acl = 'private'  # Files are private by default


class ArticleStorage(S3Boto3Storage):
    """
    S3 storage for article files.

    Files are stored in the 'articles/' folder in the S3 bucket.
    """
    location = 'articles'
    file_overwrite = False
    default_acl = 'private'


class PublicMediaStorage(S3Boto3Storage):
    """
    S3 storage for public media files.

    Files are stored in the 'media/' folder and are publicly accessible.
    """
    location = 'media'
    file_overwrite = False
    default_acl = 'public-read'
