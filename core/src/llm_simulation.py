#!/usr/bin/env python3
"""
LLM Writing Simulation

Simulates an LLM writing an article incrementally and getting validated
using pre-computed guideline data for FAST repeated validation.

Workflow:
1. Pre-compute guideline data ONCE (stored in database)
2. LLM writes article in chunks
3. After each chunk, validate FAST using pre-computed data
4. Provide feedback to LLM
5. Repeat until complete
"""

import time
from typing import List
from guideline_storage import GuidelinePreprocessor, save_guideline_to_json, load_guideline_from_json
from fast_validator import FastArticleValidator


class LLMArticleWriter:
    """
    Simulates an LLM writing an article incrementally.
    """

    def __init__(self):
        # Simulated LLM responses (chunks of article)
        self.chunks = [
            # Chunk 1: Title and intro
            """# Hemp Shoes: The Sustainable Footwear Revolution

Hemp shoes are becoming increasingly popular as an eco-friendly alternative to traditional footwear. These sustainable shoes are made from natural hemp fibers, offering both comfort and environmental benefits.
""",
            # Chunk 2: Benefits
            """
## Benefits of Hemp Shoes

Hemp shoes provide numerous advantages for conscious consumers. The natural fibers used in hemp shoes are biodegradable and require minimal water to grow. Sustainable footwear made from hemp is also incredibly durable, lasting years with proper care.

Many people find hemp shoes comfortable for daily wear. The breathable hemp material keeps feet cool while providing adequate support.
""",
            # Chunk 3: Durability section
            """
## Are Hemp Shoes Durable?

Yes, hemp shoes are remarkably durable. Hemp fibers are among the strongest natural fibers available, making hemp shoes resistant to wear and tear. With proper maintenance, sustainable footwear made from hemp can outlast conventional shoes.

The eco-friendly construction of hemp shoes doesn't compromise on quality. In fact, many users report that their hemp shoes become more comfortable over time as the fibers soften naturally.
""",
            # Chunk 4: Care instructions
            """
## How to Clean Hemp Shoes

Caring for your sustainable footwear is simple. Hemp shoes can be hand-washed with mild soap and water. Avoid using harsh chemicals that might damage the natural hemp fibers.

For best results, air-dry your hemp shoes away from direct sunlight. This eco-friendly approach to shoe care maintains the integrity of the hemp material while extending the life of your sustainable footwear.
""",
            # Chunk 5: Conclusion
            """
## Why Choose Hemp Shoes?

Hemp shoes represent the future of eco-friendly fashion. By choosing sustainable footwear made from hemp, you're supporting environmentally responsible manufacturing while enjoying comfortable, durable shoes.

Whether you're looking for casual sneakers or dress shoes, hemp shoes offer a stylish and sustainable solution. Make the switch to eco-friendly hemp shoes today and experience the difference that sustainable footwear can make.
"""
        ]

        self.current_content = ""
        self.chunk_index = 0

    def write_next_chunk(self) -> str:
        """
        Simulate LLM writing the next chunk of the article.

        Returns:
            The newly added chunk
        """
        if self.chunk_index >= len(self.chunks):
            return ""

        chunk = self.chunks[self.chunk_index]
        self.current_content += chunk
        self.chunk_index += 1

        return chunk

    def get_full_content(self) -> str:
        """Get the full article content written so far"""
        return self.current_content

    def has_more_chunks(self) -> bool:
        """Check if there are more chunks to write"""
        return self.chunk_index < len(self.chunks)


def simulate_llm_writing_with_validation():
    """
    Main simulation: LLM writes article with real-time validation
    """
    print("=" * 80)
    print("LLM ARTICLE WRITING SIMULATION WITH REAL-TIME VALIDATION")
    print("=" * 80)

    # ========================================================================
    # STEP 1: PRE-COMPUTE GUIDELINE DATA (DONE ONCE, STORED IN DATABASE)
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: PRE-COMPUTE GUIDELINE DATA (DONE ONCE)")
    print("=" * 80)

    guideline_text = """## CONTENT STRUCTURE
* Paragraphs: 8 - 15
* Images: 0 - 3
* Headings: 4 - 8
* Characters: 1500 - 3000
* Words: 250 - 500

## IMPORTANT TERMS TO USE
* hemp shoes: 8 - 15
* sustainable footwear: 3 - 8
* eco-friendly: 4 - 10

## QUESTIONS TO ANSWER
* Are hemp shoes durable?
* How to clean hemp shoes?
"""

    # Preprocess ONCE
    print("\n📝 Preprocessing guideline (happens ONCE)...")
    start_time = time.time()

    preprocessor = GuidelinePreprocessor()
    stored_guideline = preprocessor.process_guideline(
        guideline_source=guideline_text,
        guideline_name="Hemp Shoes Article Guide",
        guideline_id="guideline_preprocessed"
    )

    preprocess_time = (time.time() - start_time) * 1000  # Convert to ms

    # Save to JSON (simulates database storage)
    save_guideline_to_json(stored_guideline, "guideline_preprocessed.json")

    print(f"✓ Guideline preprocessed in {preprocess_time:.2f}ms")
    print(f"✓ Saved to database (JSON file)")
    print(f"\n   Keywords with Q3 targets:")
    for keyword, data in stored_guideline.keywords_q3.items():
        print(f"      '{keyword}': target={data['target']} (range: {data['min']}-{data['max']})")

    # ========================================================================
    # STEP 2: LOAD PRE-COMPUTED DATA (FROM DATABASE)
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: LOAD PRE-COMPUTED DATA FROM DATABASE")
    print("=" * 80)

    print("\n📥 Loading guideline from database...")
    start_time = time.time()

    # Simulate loading from database
    loaded_guideline = load_guideline_from_json("guideline_preprocessed.json")

    load_time = (time.time() - start_time) * 1000

    print(f"✓ Loaded in {load_time:.2f}ms")

    # Create validator (reuse for all validations)
    validator = FastArticleValidator(loaded_guideline, target_quartile="Q3")
    print(f"✓ Validator initialized with Q3 targets")

    # ========================================================================
    # STEP 3: SIMULATE LLM WRITING WITH VALIDATION
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: LLM WRITES ARTICLE WITH REAL-TIME VALIDATION")
    print("=" * 80)

    llm = LLMArticleWriter()
    validation_times = []

    print("\n🤖 LLM starts writing...\n")

    chunk_num = 1
    while llm.has_more_chunks():
        # LLM writes next chunk
        chunk = llm.write_next_chunk()

        print(f"\n{'─' * 80}")
        print(f"CHUNK {chunk_num}: LLM writes ({len(chunk)} chars)")
        print(f"{'─' * 80}")
        print(f"{chunk[:100]}..." if len(chunk) > 100 else chunk)

        # FAST validation using pre-computed data
        print(f"\n⚡ Validating (using pre-computed data)...")
        start_time = time.time()

        result = validator.validate(llm.get_full_content())

        validation_time = (time.time() - start_time) * 1000
        validation_times.append(validation_time)

        print(f"✓ Validated in {validation_time:.2f}ms")

        # Show feedback
        print(f"\n📊 Validation Results:")
        print(f"   Score: {result.overall_score}/100")
        print(f"   Summary: {result.summary}")
        print(f"   Keywords at target: {result.keywords_at_target}/{result.total_keywords}")

        # Show critical feedback
        critical_feedback = [kf for kf in result.keyword_feedback if kf.priority == "critical"]
        if critical_feedback:
            print(f"\n   🔴 Critical Issues:")
            for kf in critical_feedback:
                print(f"      • '{kf.keyword}': {kf.current} (need {kf.target}, delta: {kf.delta:+d})")

        # Show high priority feedback
        high_feedback = [kf for kf in result.keyword_feedback if kf.priority == "high"]
        if high_feedback:
            print(f"\n   🟠 High Priority:")
            for kf in high_feedback[:3]:  # Show top 3
                print(f"      • '{kf.keyword}': {kf.current} (target {kf.target}, delta: {kf.delta:+d})")

        # Show structure feedback
        if result.structure_feedback:
            print(f"\n   📐 Structure:")
            for feedback in result.structure_feedback[:2]:  # Show top 2
                print(f"      • {feedback}")

        chunk_num += 1
        time.sleep(0.5)  # Simulate time between LLM responses

    # ========================================================================
    # STEP 4: FINAL VALIDATION & STATISTICS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: FINAL RESULTS & PERFORMANCE STATISTICS")
    print("=" * 80)

    final_result = validator.validate(llm.get_full_content())

    print(f"\n📝 Final Article Stats:")
    print(f"   Total length: {len(llm.get_full_content())} characters")
    print(f"   Chunks written: {chunk_num - 1}")

    print(f"\n🎯 Final Validation:")
    print(f"   Overall Score: {final_result.overall_score}/100")
    print(f"   Keywords at target: {final_result.keywords_at_target}/{final_result.total_keywords}")
    print(f"   Keywords in range: {final_result.keywords_within_range}/{final_result.total_keywords}")
    print(f"   Structure valid: {'✓ Yes' if final_result.structure_valid else '✗ No'}")

    print(f"\n⚡ Performance Statistics:")
    print(f"   Guideline preprocessing: {preprocess_time:.2f}ms (done ONCE)")
    print(f"   Database load time: {load_time:.2f}ms (done ONCE)")
    print(f"   Validations performed: {len(validation_times)}")
    print(f"   Average validation time: {sum(validation_times)/len(validation_times):.2f}ms")
    print(f"   Min validation time: {min(validation_times):.2f}ms")
    print(f"   Max validation time: {max(validation_times):.2f}ms")
    print(f"   Total validation time: {sum(validation_times):.2f}ms")

    print(f"\n💡 Key Takeaways:")
    print(f"   ✓ Guideline preprocessed ONCE: {preprocess_time:.2f}ms")
    print(f"   ✓ Each validation: ~{sum(validation_times)/len(validation_times):.2f}ms (FAST!)")
    print(f"   ✓ No re-parsing or re-calculation needed")
    print(f"   ✓ Perfect for real-time LLM feedback")

    # Show final keyword counts
    print(f"\n📊 Final Keyword Analysis:")
    content_lower = llm.get_full_content().lower()
    for keyword, data in loaded_guideline.keywords_q3.items():
        import re
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        count = len(re.findall(pattern, content_lower))
        status = "✓" if count == data['target'] else "•"
        print(f"   {status} '{keyword}': {count} (target: {data['target']}, range: {data['min']}-{data['max']})")

    return final_result


def example_django_workflow():
    """
    Show example Django workflow with database
    """
    print("\n\n" + "=" * 80)
    print("EXAMPLE: REAL DJANGO WORKFLOW")
    print("=" * 80)

    print("""
# ============================================================================
# ONE-TIME SETUP: Preprocess and save guideline to database
# ============================================================================

from guideline_storage import GuidelinePreprocessor
from myapp.models import Guideline

# Parse and preprocess guideline ONCE
preprocessor = GuidelinePreprocessor()
stored = preprocessor.process_guideline(
    guideline_source=guideline_text_or_file,
    guideline_name="Hemp Shoes Guide",
    guideline_id="hemp_001"
)

# Save to Django database (ONCE)
Guideline.objects.create(
    id=stored.id,
    name=stored.name,
    paragraphs_min=stored.paragraphs_min,
    paragraphs_max=stored.paragraphs_max,
    # ... other structure fields ...
    keywords_q1=stored.keywords_q1,  # JSONField
    keywords_q2=stored.keywords_q2,  # JSONField
    keywords_q3=stored.keywords_q3,  # JSONField
    keywords_q4=stored.keywords_q4,  # JSONField
    other_terms=stored.other_terms,
    questions=stored.questions,
    notes=stored.notes
)

# ============================================================================
# REPEATED: Fast validation as LLM writes
# ============================================================================

from fast_validator import FastArticleValidator
from guideline_storage import StoredGuideline
from myapp.models import Guideline

# Load guideline from database
guideline_db = Guideline.objects.get(id="hemp_001")

# Convert to StoredGuideline object
stored_guideline = StoredGuideline(
    id=guideline_db.id,
    name=guideline_db.name,
    paragraphs_min=guideline_db.paragraphs_min,
    paragraphs_max=guideline_db.paragraphs_max,
    # ... other fields ...
    keywords_q1=guideline_db.keywords_q1,
    keywords_q2=guideline_db.keywords_q2,
    keywords_q3=guideline_db.keywords_q3,
    keywords_q4=guideline_db.keywords_q4,
    other_terms=guideline_db.other_terms,
    questions=guideline_db.questions,
    notes=guideline_db.notes
)

# Create validator ONCE per session
validator = FastArticleValidator(stored_guideline, target_quartile="Q3")

# Validate article as LLM writes (FAST - called many times)
def validate_llm_output(article_text):
    result = validator.validate(article_text)
    return result.to_dict()

# Example API endpoint
@api_view(['POST'])
def validate_article(request):
    article_text = request.data.get('content')
    guideline_id = request.data.get('guideline_id')

    # Load from cache or database
    validator = get_or_create_validator(guideline_id, target_quartile="Q3")

    # FAST validation
    result = validator.validate(article_text)

    return Response(result.to_dict())
    """)


if __name__ == "__main__":
    # Run the simulation
    result = simulate_llm_writing_with_validation()

    # Show Django example
    example_django_workflow()

    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE!")
    print("=" * 80)
