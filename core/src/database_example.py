#!/usr/bin/env python3
"""
Example usage of database parsing functionality for GuidelineParser and ContentPipeline.

Demonstrates how to use guidelines from:
1. Raw text strings (from database)
2. Dictionary/JSON data (from database)
3. Django model objects
4. Direct ContentRequirements objects
"""

from guideline_parser import GuidelineParser, ContentRequirements
from content_pipeline import ContentPipeline, QuartileTarget


def example_1_text_from_database():
    """
    Example 1: Parse guidelines from raw text string
    (e.g., text stored in a database TEXT field)
    """
    print("=" * 70)
    print("EXAMPLE 1: PARSING FROM RAW TEXT (DATABASE)")
    print("=" * 70)

    # Simulate text retrieved from database
    guideline_text = """## CONTENT STRUCTURE
* Paragraphs: 5 - 10
* Images: 2 - 5
* Headings: 3 - 8
* Characters: 1000 - 3000
* Words: 200 - 500

## IMPORTANT TERMS TO USE
* hemp shoes: 5 - 10
* sustainable footwear: 2 - 5
* eco-friendly: 3 - 8

## OTHER RELEVANT TERMS
* natural fibers
* biodegradable
* ethical fashion

## QUESTIONS TO ANSWER
* Are hemp shoes durable?
* How are hemp shoes made?
* Are hemp shoes comfortable?

## NOTES
Focus on sustainability and environmental benefits.
"""

    # Method 1: Using GuidelineParser directly
    print("\n📝 Method 1: GuidelineParser.parse_from_text()")
    parser = GuidelineParser()
    requirements = parser.parse_from_text(guideline_text)

    print(f"   ✓ Parsed {len(requirements.important_terms)} keywords")
    print(f"   ✓ Parsed {len(requirements.questions)} questions")
    print(f"   ✓ Notes: {requirements.notes[:50]}...")

    # Method 2: Using ContentPipeline with text
    print("\n📝 Method 2: ContentPipeline with text (auto-detect)")
    pipeline = ContentPipeline(
        guidelines_source=guideline_text,
        quartile_target=QuartileTarget.Q3_UPPER,
        verbose=False
    )
    print(f"   ✓ Pipeline initialized with {len(pipeline.requirements.important_terms)} keywords")

    # Method 3: Explicit source_type
    print("\n📝 Method 3: ContentPipeline with explicit source_type='text'")
    pipeline2 = ContentPipeline(
        guidelines_source=guideline_text,
        quartile_target=QuartileTarget.Q2_MEDIAN,
        verbose=False,
        source_type="text"
    )
    print(f"   ✓ Pipeline initialized")

    return requirements


def example_2_dict_from_database():
    """
    Example 2: Parse guidelines from dictionary/JSON data
    (e.g., JSON field in database or structured data)
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 2: PARSING FROM DICTIONARY (STRUCTURED DATABASE)")
    print("=" * 70)

    # Simulate structured data from database
    guideline_data = {
        'notes': 'Focus on eco-friendly and sustainable aspects',
        'paragraphs': (5, 15),
        'images': (2, 5),
        'headings': (3, 8),
        'characters': (1500, 3500),
        'words': (250, 600),
        'important_terms': {
            'hemp shoes': (5, 12),
            'sustainable': (3, 8),
            'eco-friendly': (2, 6),
            'natural fibers': (1, 4)
        },
        'other_terms': ['biodegradable', 'ethical', 'vegan'],
        'questions': [
            'Are hemp shoes waterproof?',
            'How long do hemp shoes last?',
            'Where can I buy hemp shoes?'
        ]
    }

    # Method 1: Using GuidelineParser
    print("\n📝 Method 1: GuidelineParser.parse_from_dict()")
    parser = GuidelineParser()
    requirements = parser.parse_from_dict(guideline_data)

    print(f"   ✓ Parsed {len(requirements.important_terms)} keywords")
    print(f"   ✓ Word range: {requirements.words}")

    # Method 2: Using ContentPipeline
    print("\n📝 Method 2: ContentPipeline with dict")
    pipeline = ContentPipeline(
        guidelines_source=guideline_data,
        quartile_target=QuartileTarget.Q3_UPPER,
        verbose=False,
        source_type="dict"
    )
    print(f"   ✓ Pipeline initialized")

    return requirements


def example_3_django_model_simulation():
    """
    Example 3: Parse guidelines from Django model object
    Simulates a Django model with guideline data
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 3: PARSING FROM DJANGO MODEL (ORM)")
    print("=" * 70)

    # Simulate Django model with raw text content
    class GuidelineModelWithText:
        """Simulates Django model with 'content' field"""
        content = """## CONTENT STRUCTURE
* Paragraphs: 8 - 12
* Images: 3 - 6
* Headings: 4 - 10
* Characters: 2000 - 4000
* Words: 350 - 700

## IMPORTANT TERMS TO USE
* hemp clothing: 4 - 10
* sustainable fashion: 3 - 7
"""

    # Simulate Django model with structured fields
    class GuidelineModelWithFields:
        """Simulates Django model with individual fields"""
        notes = "Emphasize sustainability"
        paragraphs_min = 5
        paragraphs_max = 10
        images_min = 2
        images_max = 4
        headings_min = 3
        headings_max = 8
        characters_min = 1500
        characters_max = 3000
        words_min = 250
        words_max = 500
        important_terms = {
            'hemp': (10, 20),
            'sustainable': (5, 10)
        }
        other_terms = ['eco-friendly', 'natural']
        questions = ['What is hemp?', 'Is hemp sustainable?']

    # Method 1: Model with text content
    print("\n📝 Method 1: Model with 'content' field")
    parser = GuidelineParser()
    model1 = GuidelineModelWithText()
    requirements1 = parser.parse_from_model(model1)

    print(f"   ✓ Parsed {len(requirements1.important_terms)} keywords")
    print(f"   ✓ Keywords: {list(requirements1.important_terms.keys())}")

    # Method 2: Model with structured fields
    print("\n📝 Method 2: Model with structured fields")
    model2 = GuidelineModelWithFields()
    requirements2 = parser.parse_from_model(model2)

    print(f"   ✓ Parsed {len(requirements2.important_terms)} keywords")
    print(f"   ✓ Notes: {requirements2.notes}")
    print(f"   ✓ Paragraphs range: {requirements2.paragraphs}")

    # Method 3: Using ContentPipeline with model
    print("\n📝 Method 3: ContentPipeline with model")
    pipeline = ContentPipeline(
        guidelines_source=model1,
        quartile_target=QuartileTarget.Q2_MEDIAN,
        verbose=False,
        source_type="model"
    )
    print(f"   ✓ Pipeline initialized")

    return requirements1, requirements2


def example_4_content_requirements_object():
    """
    Example 4: Pass pre-parsed ContentRequirements object
    Useful when you've already parsed or constructed the requirements
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 4: USING PRE-PARSED CONTENTREQUIREMENTS OBJECT")
    print("=" * 70)

    # Create ContentRequirements object manually
    requirements = ContentRequirements(
        notes="Custom notes from application logic",
        paragraphs=(10, 20),
        images=(3, 6),
        headings=(5, 10),
        characters=(2500, 5000),
        words=(400, 900),
        important_terms={
            'sustainable hemp': (5, 12),
            'eco-friendly shoes': (3, 8)
        },
        other_terms=['renewable', 'biodegradable'],
        questions=['Why choose hemp?', 'How is hemp processed?']
    )

    print("\n📝 Using ContentPipeline with ContentRequirements object")
    pipeline = ContentPipeline(
        guidelines_source=requirements,
        quartile_target=QuartileTarget.Q4_MAX,
        verbose=False
    )
    print(f"   ✓ Pipeline initialized")
    print(f"   ✓ Keywords: {list(pipeline.requirements.important_terms.keys())}")

    return requirements


def example_5_real_world_django_integration():
    """
    Example 5: Realistic Django integration pattern
    Shows how you might use this in a Django view or service
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 5: REALISTIC DJANGO INTEGRATION")
    print("=" * 70)

    print("\n📝 Typical Django usage pattern:")
    print("""
    # In your Django view or service:

    from myapp.models import Guideline, Article
    from content_pipeline import ContentPipeline, QuartileTarget

    def analyze_article_view(request, article_id):
        # Get guideline from database
        guideline = Guideline.objects.get(id=request.POST['guideline_id'])
        article = Article.objects.get(id=article_id)

        # Option 1: If guideline has 'content' field with raw text
        pipeline = ContentPipeline(
            guidelines_source=guideline,
            quartile_target=QuartileTarget.Q3_UPPER,
            source_type="model"
        )

        # Option 2: If guideline has structured fields
        pipeline = ContentPipeline(
            guidelines_source=guideline,
            quartile_target=QuartileTarget.Q3_UPPER,
            source_type="model"
        )

        # Option 3: If you store as JSON in database
        guideline_data = guideline.data  # JSONField
        pipeline = ContentPipeline(
            guidelines_source=guideline_data,
            quartile_target=QuartileTarget.Q3_UPPER,
            source_type="dict"
        )

        # Analyze the article
        result = pipeline.analyze_article(article.file_path)

        # Save results to database
        article.quality_score = result.overall_quality_score
        article.status = result.overall_status
        article.save()

        return JsonResponse(result.to_dict())
    """)

    print("\n✓ Integration pattern documented")


def example_6_auto_detection():
    """
    Example 6: Auto-detection of source types
    Shows how ContentPipeline automatically detects the source type
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 6: AUTO-DETECTION OF SOURCE TYPES")
    print("=" * 70)

    # Different source types, all auto-detected
    sources = {
        "File path": "test_guidelines.txt",
        "Raw text": "## CONTENT STRUCTURE\n* Paragraphs: 5 - 10\n",
        "Dictionary": {'paragraphs': (5, 10), 'important_terms': {}},
    }

    for name, source in sources.items():
        try:
            print(f"\n📝 Testing: {name}")
            # Note: File might not exist, which is OK for this example
            pipeline = ContentPipeline(
                guidelines_source=source,
                verbose=False,
                source_type="auto"  # Auto-detect
            )
            print(f"   ✓ Auto-detected and parsed successfully")
        except Exception as e:
            print(f"   ℹ️  {str(e)[:60]}...")

    print("\n✓ Auto-detection tested")


def main():
    """Run all examples"""
    print("\n🚀 DATABASE INTEGRATION EXAMPLES")
    print("=" * 70)

    try:
        # Run examples
        example_1_text_from_database()
        example_2_dict_from_database()
        example_3_django_model_simulation()
        example_4_content_requirements_object()
        example_5_real_world_django_integration()
        example_6_auto_detection()

        # Summary
        print("\n\n" + "=" * 70)
        print("SUMMARY - DATABASE INTEGRATION")
        print("=" * 70)

        print("\n✅ GuidelineParser now supports:")
        print("   • parse_file(filepath) - Original file-based parsing")
        print("   • parse_from_text(text) - Raw text from database")
        print("   • parse_from_dict(data) - Structured dictionary/JSON")
        print("   • parse_from_model(model) - Django/ORM model objects")

        print("\n✅ ContentPipeline now accepts:")
        print("   • File paths (auto-detected)")
        print("   • Raw text strings (auto-detected)")
        print("   • Dictionary/JSON data (auto-detected)")
        print("   • Django model objects (specify source_type='model')")
        print("   • ContentRequirements objects (auto-detected)")

        print("\n💡 Usage tips:")
        print("   • Use source_type='auto' for automatic detection (default)")
        print("   • Use explicit source_type for better performance")
        print("   • All existing file-based code remains fully compatible")

        print("\n🎯 Django Integration:")
        print("   • Fetch guideline from database")
        print("   • Pass directly to ContentPipeline")
        print("   • No need to save temp files")
        print("   • Works with text fields, JSON fields, or structured models")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
