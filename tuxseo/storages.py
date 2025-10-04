from storages.backends.s3boto3 import S3Boto3Storage


class CustomS3Boto3Storage(S3Boto3Storage):
    def url(self, name, parameters=None, expire=None):
        url = super().url(name, parameters, expire)
        if url.startswith("http://minio:9000"):
            return url.replace("http://minio:9000", "http://localhost:9000")
        return url
