from core.utils import replace_placeholders


class MockBlogPost:
    def __init__(self):
        self.title = "Test Blog Post"
        self.slug = "test-blog-post"
        self.description = "This is a test description"
        self.id = 123

    @property
    def nested(self):
        return MockNested()


class MockNested:
    def __init__(self):
        self.value = "nested_value"


class TestReplacePlaceholders:
    def test_replace_placeholders_with_simple_string(self):
        blog_post = MockBlogPost()
        data = "{{ title }}"
        result = replace_placeholders(data, blog_post)
        assert result == "Test Blog Post"

    def test_replace_placeholders_with_multiple_placeholders_in_string(self):
        blog_post = MockBlogPost()
        data = "Title: {{ title }}, Slug: {{ slug }}"
        result = replace_placeholders(data, blog_post)
        assert result == "Title: Test Blog Post, Slug: test-blog-post"

    def test_replace_placeholders_with_whitespace_in_placeholder(self):
        blog_post = MockBlogPost()
        data = "{{  title  }}"
        result = replace_placeholders(data, blog_post)
        assert result == "Test Blog Post"

    def test_replace_placeholders_with_nonexistent_attribute(self):
        blog_post = MockBlogPost()
        data = "{{ nonexistent }}"
        result = replace_placeholders(data, blog_post)
        assert result == "{{ nonexistent }}"

    def test_replace_placeholders_with_dict(self):
        blog_post = MockBlogPost()
        data = {
            "title": "{{ title }}",
            "slug": "{{ slug }}",
            "description": "{{ description }}",
        }
        result = replace_placeholders(data, blog_post)
        assert result == {
            "title": "Test Blog Post",
            "slug": "test-blog-post",
            "description": "This is a test description",
        }

    def test_replace_placeholders_with_nested_dict(self):
        blog_post = MockBlogPost()
        data = {
            "post": {
                "title": "{{ title }}",
                "metadata": {
                    "slug": "{{ slug }}",
                },
            },
        }
        result = replace_placeholders(data, blog_post)
        assert result == {
            "post": {
                "title": "Test Blog Post",
                "metadata": {
                    "slug": "test-blog-post",
                },
            },
        }

    def test_replace_placeholders_with_list(self):
        blog_post = MockBlogPost()
        data = ["{{ title }}", "{{ slug }}", "{{ description }}"]
        result = replace_placeholders(data, blog_post)
        assert result == ["Test Blog Post", "test-blog-post", "This is a test description"]

    def test_replace_placeholders_with_nested_list(self):
        blog_post = MockBlogPost()
        data = [
            {"title": "{{ title }}"},
            {"slug": "{{ slug }}"},
        ]
        result = replace_placeholders(data, blog_post)
        assert result == [
            {"title": "Test Blog Post"},
            {"slug": "test-blog-post"},
        ]

    def test_replace_placeholders_with_mixed_data_structure(self):
        blog_post = MockBlogPost()
        data = {
            "posts": [
                {"title": "{{ title }}", "id": "{{ id }}"},
                {"slug": "{{ slug }}"},
            ],
            "metadata": {
                "description": "{{ description }}",
            },
        }
        result = replace_placeholders(data, blog_post)
        assert result == {
            "posts": [
                {"title": "Test Blog Post", "id": "123"},
                {"slug": "test-blog-post"},
            ],
            "metadata": {
                "description": "This is a test description",
            },
        }

    def test_replace_placeholders_with_nested_attribute(self):
        blog_post = MockBlogPost()
        data = "{{ nested.value }}"
        result = replace_placeholders(data, blog_post)
        assert result == "nested_value"

    def test_replace_placeholders_with_nonexistent_nested_attribute(self):
        blog_post = MockBlogPost()
        data = "{{ nested.nonexistent }}"
        result = replace_placeholders(data, blog_post)
        assert result == "{{ nested.nonexistent }}"

    def test_replace_placeholders_with_non_string_value(self):
        blog_post = MockBlogPost()
        data = {"title": "{{ title }}", "id": 456}
        result = replace_placeholders(data, blog_post)
        assert result == {"title": "Test Blog Post", "id": 456}

    def test_replace_placeholders_with_empty_string(self):
        blog_post = MockBlogPost()
        data = ""
        result = replace_placeholders(data, blog_post)
        assert result == ""

    def test_replace_placeholders_with_empty_dict(self):
        blog_post = MockBlogPost()
        data = {}
        result = replace_placeholders(data, blog_post)
        assert result == {}

    def test_replace_placeholders_with_empty_list(self):
        blog_post = MockBlogPost()
        data = []
        result = replace_placeholders(data, blog_post)
        assert result == []

    def test_replace_placeholders_with_no_placeholders(self):
        blog_post = MockBlogPost()
        data = "This is a regular string without placeholders"
        result = replace_placeholders(data, blog_post)
        assert result == "This is a regular string without placeholders"

    def test_replace_placeholders_with_integer(self):
        blog_post = MockBlogPost()
        data = 42
        result = replace_placeholders(data, blog_post)
        assert result == 42

    def test_replace_placeholders_with_boolean(self):
        blog_post = MockBlogPost()
        data = True
        result = replace_placeholders(data, blog_post)
        assert result is True

    def test_replace_placeholders_with_none(self):
        blog_post = MockBlogPost()
        data = None
        result = replace_placeholders(data, blog_post)
        assert result is None

    def test_replace_placeholders_with_partial_placeholder(self):
        blog_post = MockBlogPost()
        data = "{{ title } and more"
        result = replace_placeholders(data, blog_post)
        assert result == "{{ title } and more"

    def test_replace_placeholders_with_multiple_same_placeholder(self):
        blog_post = MockBlogPost()
        data = "{{ title }} - {{ title }} - {{ title }}"
        result = replace_placeholders(data, blog_post)
        assert result == "Test Blog Post - Test Blog Post - Test Blog Post"
