#!/usr/bin/env python3
"""
Complete usage examples for the quartile action generator
Shows both file-based and text-based input
"""

from pathlib import Path
import json

from guideline_parser import GuidelineParser
from keyword_analysis import ImprovedArticleValidator
from quartile_analyzer import KeywordQuartileAnalyzer
from quartile_action_generator import QuartileActionGenerator, QuartileTarget
from content_pipeline import ContentPipeline


def example_1_with_files():
    """
    Example 1: Using file paths
    Most common use case
    """
    print("=" * 70)
    print("EXAMPLE 1: USING FILES")
    print("=" * 70)
    
    # File paths
    script_dir = Path(__file__).resolve().parent
    guidelines_file = script_dir / "test_guidelines.txt"
    article_file = script_dir / "test_article.txt"
    
    # print(f"\n📄 Input files:")
    # print(f"   Guidelines: {guidelines_file}")
    # print(f"   Article: {article_file}")
    
    # Step 1: Parse guidelines
    print("\n🔍 Step 1: Parse guidelines")
    parser = GuidelineParser()
    requirements = parser.parse_file(str(guidelines_file))
    
    print(f"   ✓ Found {len(requirements.important_terms)} keywords")
    print(f"   ✓ Found {len(requirements.questions)} questions")
    
    # Step 2: Load article content
    print("\n🔍 Step 2: Load article")
    with open(article_file, 'r', encoding='utf-8') as f:
        article_content = f.read()
    
    print(f"   ✓ Loaded {len(article_content)} characters")
    
    # Step 3: Validate article
    print("\n🔍 Step 3: Validate article")
    validator = ImprovedArticleValidator(requirements)
    validation_results = validator.validate_all(article_content)
    validation_summary = validator.get_summary(validation_results)
    
    print(f"   ✓ Pass rate: {validation_summary['pass_rate']:.1f}%")
    print(f"   ✓ {validation_summary['passed']}/{validation_summary['total_checks']} checks passed")
    
    # Step 4: Analyze keywords
    print("\n🔍 Step 4: Analyze keywords")
    analyzer = KeywordQuartileAnalyzer(requirements.important_terms)
    raw_metrics = analyzer.analyze_all_keywords(article_content)
    
    print(f"   ✓ Analyzed {len(raw_metrics)} keywords")
    
    # Step 5: Get structured validation results
    print("\n🔍 Step 5: Structure validation results")
    temp_pipeline = ContentPipeline(str(guidelines_file), verbose=False)
    structured_validation = temp_pipeline._structure_validation_results(validation_results)
    
    print(f"   ✓ Structured {len(structured_validation)} validation results")
    
    # Step 6: Generate Q2 actions
    print("\n🔍 Step 6: Generate Q2 actions")
    generator = QuartileActionGenerator(QuartileTarget.Q1)
    output = generator.generate(raw_metrics, structured_validation)
    
    print(f"   ✓ Generated {output.total_actions} actions")
    print(f"   ✓ Priority breakdown: {output.summary['by_priority']}")
    
    # Step 7: Output JSON
    print("\n📤 Step 7: JSON Output")
    json_output = output.to_json(minified=False)
    
    # Show first 500 chars
    print(json_output)
    
    # Save to file
    output_file = script_dir / "output_example1.json"
    with open(output_file, 'w') as f:
        f.write(json_output)
    
    print(f"\n✓ Saved to: {output_file}")
    
    return output


def example_2_with_text():
    """
    Example 2: Using text directly (no files)
    Useful for API/web applications
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 2: USING TEXT DIRECTLY")
    print("=" * 70)
    
    # Guidelines as text
    guidelines_text = """## CONTENT STRUCTURE
                * Paragraphs: 5 - 10
                * Images: 2 - 5
                * Headings: 3 - 8
                * Characters: 1000 - 3000
                * Words: 200 - 500

                ## IMPORTANT TERMS TO USE
                * hemp shoes: 5 - 10
                * sustainable: 2 - 5
                * eco-friendly: 1 - 3

                ## QUESTIONS TO ANSWER
                * Are hemp shoes durable?
                * Are hemp shoes comfortable?
            """
    
    # Article as text
    article_text = """# Hemp Shoes Guide

            Hemp shoes are an eco-friendly alternative to traditional footwear. These sustainable shoes are made from hemp fibers, which are both durable and comfortable.

            Hemp shoes have gained popularity due to their environmental benefits. The hemp plant requires less water than cotton and grows quickly without pesticides.

            Many people find hemp shoes to be very comfortable for daily wear. The natural fibers allow your feet to breathe while providing adequate support.

            Are hemp shoes durable? Yes, hemp fibers are known for their strength and longevity. Hemp shoes can last for years with proper care.

            Hemp shoes are also lightweight and flexible, making them ideal for various activities. Whether you're walking, hiking, or just running errands, hemp shoes provide comfort and style.
"""
    
    print("\n📝 Input text:")
    print(f"   Guidelines: {len(guidelines_text)} chars")
    print(f"   Article: {len(article_text)} chars")
    
    # Step 1: Create temp files (or use in-memory parsing)
    print("\n🔍 Step 1: Parse guidelines from text")
    
    # Save to temp file for parsing
    temp_dir = Path(__file__).resolve().parent / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    temp_guidelines = temp_dir / "temp_guidelines.txt"
    with open(temp_guidelines, 'w') as f:
        f.write(guidelines_text)
    
    parser = GuidelineParser()
    requirements = parser.parse_file(str(temp_guidelines))
    
    print(f"   ✓ Found {len(requirements.important_terms)} keywords")
    
    # Step 2: Validate article
    print("\n🔍 Step 2: Validate article")
    validator = ImprovedArticleValidator(requirements)
    validation_results = validator.validate_all(article_text)
    validation_summary = validator.get_summary(validation_results)
    
    print(f"   ✓ Pass rate: {validation_summary['pass_rate']:.1f}%")
    
    # Step 3: Analyze keywords
    print("\n🔍 Step 3: Analyze keywords")
    analyzer = KeywordQuartileAnalyzer(requirements.important_terms)
    raw_metrics = analyzer.analyze_all_keywords(article_text)
    
    print(f"   ✓ Analyzed {len(raw_metrics)} keywords")
    
    # Show keyword analysis
    print("\n   Keyword breakdown:")
    for m in raw_metrics:
        print(f"      '{m.keyword}': {m.current_count} (range: {m.min_required}-{m.max_allowed})")
    
    # Step 4: Structure validation
    print("\n🔍 Step 4: Structure validation results")
    temp_pipeline = ContentPipeline(str(temp_guidelines), verbose=False)
    structured_validation = temp_pipeline._structure_validation_results(validation_results)
    
    # Step 5: Generate Q3 actions
    print("\n🔍 Step 5: Generate Q3 actions")
    generator = QuartileActionGenerator(QuartileTarget.Q3)
    output = generator.generate(raw_metrics, structured_validation)
    
    print(f"   ✓ Generated {output.total_actions} actions")
    
    # Step 6: Show actions
    print("\n📋 Actions:")
    json_data = output.to_dict()
    
    for i, action in enumerate(json_data['actions'][:5], 1):
        print(f"   {i}. {action['type'].upper()}: '{action['target']}'")
        print(f"      Current: {action['current']} → Required: {action['required']} (Δ {action['delta']:+d})")
        print(f"      Priority: {action['priority']}")
    
    if len(json_data['actions']) > 5:
        print(f"   ... and {len(json_data['actions']) - 5} more actions")
    
    # Cleanup
    temp_guidelines.unlink()
    temp_dir.rmdir()
    
    return output


def example_3_all_quartiles():
    """
    Example 3: Generate actions for all quartiles
    Compare different targets
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 3: ALL QUARTILES COMPARISON")
    print("=" * 70)
    
    # Setup
    script_dir = Path(__file__).resolve().parent
    guidelines_file = script_dir / "test_guidelines.txt"
    article_file = script_dir / "test_article.txt"
    
    print(f"\n📄 Files: {guidelines_file.name}, {article_file.name}")
    
    # Parse and analyze once
    parser = GuidelineParser()
    requirements = parser.parse_file(str(guidelines_file))
    
    with open(article_file, 'r') as f:
        content = f.read()
    
    validator = ImprovedArticleValidator(requirements)
    validation_results = validator.validate_all(content)
    
    analyzer = KeywordQuartileAnalyzer(requirements.important_terms)
    raw_metrics = analyzer.analyze_all_keywords(content)
    
    temp_pipeline = ContentPipeline(str(guidelines_file), verbose=False)
    structured_validation = temp_pipeline._structure_validation_results(validation_results)
    
    # Generate for all quartiles
    print("\n📊 Comparison:")
    print(f"\n{'Target':<8} {'Actions':<10} {'Critical':<10} {'High':<10} {'Medium':<10} {'Low':<10}")
    print("-" * 68)
    
    all_outputs = {}
    
    for target in [QuartileTarget.Q1, QuartileTarget.Q2, QuartileTarget.Q3, QuartileTarget.Q4]:
        generator = QuartileActionGenerator(target)
        output = generator.generate(raw_metrics, structured_validation)
        
        summary = output.summary['by_priority']
        
        print(f"{target.value:<8} {output.total_actions:<10} {summary['critical']:<10} "
              f"{summary['high']:<10} {summary['medium']:<10} {summary['low']:<10}")
        
        all_outputs[target.value] = output
    
    # Show detailed comparison for first keyword
    print("\n🔍 Keyword targets for first keyword:")
    if raw_metrics:
        first_kw = raw_metrics[0].keyword
        print(f"\n   Keyword: '{first_kw}'")
        print(f"   Current: {raw_metrics[0].current_count}")
        print(f"   Range: [{raw_metrics[0].min_required}, {raw_metrics[0].max_allowed}]")
        print(f"\n   {'Target':<8} {'Zone':<20} {'Required':<12} {'Delta':<8}")
        print("   " + "-" * 48)
        
        for target_name, output in all_outputs.items():
            # Find action for this keyword
            action = next(
                (a for a in output.actions if a['target'] == first_kw),
                None
            )
            
            if action:
                zone_start = raw_metrics[0].min_required + \
                            (raw_metrics[0].max_allowed - raw_metrics[0].min_required) * \
                            {"Q1": 0, "Q2": 0.25, "Q3": 0.5, "Q4": 0.75}[target_name]
                zone_end = raw_metrics[0].min_required + \
                          (raw_metrics[0].max_allowed - raw_metrics[0].min_required) * \
                          {"Q1": 0.25, "Q2": 0.5, "Q3": 0.75, "Q4": 1.0}[target_name]
                
                print(f"   {target_name:<8} [{zone_start:.1f}, {zone_end:.1f}]"
                      f"       {action['required']:<12} {action['delta']:+7d}")
            else:
                print(f"   {target_name:<8} (already in zone)")
    
    return all_outputs


def example_4_minimal_usage():
    """
    Example 4: Minimal usage pattern
    Quickest way to get actions
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 4: MINIMAL USAGE (QUICKEST)")
    print("=" * 70)
    
    script_dir = Path(__file__).resolve().parent
    guidelines_file = script_dir / "test_guidelines.txt"
    article_file = script_dir / "test_article.txt"
    
    print("\n💨 Quick 4-step process:\n")
    
    # Step 1: Parse guidelines
    requirements = GuidelineParser().parse_file(str(guidelines_file))
    print("✓ 1. Parsed guidelines")
    
    # Step 2: Load and validate article
    with open(article_file, 'r') as f:
        content = f.read()
    
    validator = ImprovedArticleValidator(requirements)
    validation_results = validator.validate_all(content)
    print("✓ 2. Validated article")
    
    # Step 3: Analyze keywords and structure results
    raw_metrics = KeywordQuartileAnalyzer(requirements.important_terms).analyze_all_keywords(content)
    structured_validation = ContentPipeline(str(guidelines_file), verbose=False)._structure_validation_results(validation_results)
    print("✓ 3. Analyzed keywords")
    
    # Step 4: Generate actions
    output = QuartileActionGenerator(QuartileTarget.Q2).generate(raw_metrics, structured_validation)
    print("✓ 4. Generated actions")
    
    # Get JSON
    json_output = output.to_json(minified=True)
    
    print(f"\n📦 Result: {len(json_output)} bytes of JSON")
    print(f"   {output.total_actions} actions generated")
    
    return json_output


def example_5_save_and_load():
    """
    Example 5: Save and load JSON
    For persistence and API usage
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 5: SAVE AND LOAD JSON")
    print("=" * 70)
    
    script_dir = Path(__file__).resolve().parent
    guidelines_file = script_dir / "test_guidelines.txt"
    article_file = script_dir / "test_article.txt"
    output_dir = script_dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    # Generate actions
    print("\n📝 Generating actions...")
    requirements = GuidelineParser().parse_file(str(guidelines_file))
    
    with open(article_file, 'r') as f:
        content = f.read()
    
    validator = ImprovedArticleValidator(requirements)
    validation_results = validator.validate_all(content)
    
    raw_metrics = KeywordQuartileAnalyzer(requirements.important_terms).analyze_all_keywords(content)
    structured_validation = ContentPipeline(str(guidelines_file), verbose=False)._structure_validation_results(validation_results)
    
    generator = QuartileActionGenerator(QuartileTarget.Q2)
    output = generator.generate(raw_metrics, structured_validation)
    
    print(f"✓ Generated {output.total_actions} actions")
    
    # Save minified
    minified_file = output_dir / "actions_minified.json"
    with open(minified_file, 'w') as f:
        f.write(output.to_json(minified=True))
    
    print(f"\n💾 Saved minified: {minified_file}")
    print(f"   Size: {minified_file.stat().st_size} bytes")
    
    # Save pretty
    pretty_file = output_dir / "actions_pretty.json"
    with open(pretty_file, 'w') as f:
        f.write(output.to_json(minified=False))
    
    print(f"\n💾 Saved pretty: {pretty_file}")
    print(f"   Size: {pretty_file.stat().st_size} bytes")
    
    # Load and parse
    print("\n📖 Loading JSON...")
    with open(minified_file, 'r') as f:
        loaded_data = json.load(f)
    
    print(f"✓ Loaded {loaded_data['total_actions']} actions")
    print(f"✓ Target: {loaded_data['target']}")
    print(f"✓ Summary: {loaded_data['summary']}")
    
    return loaded_data


def main():
    """Run all examples"""
    
    try:
        # Example 1: Files
        output1 = example_1_with_files()
        
        # Example 2: Text
        # output2 = example_2_with_text()
        
        # # Example 3: All quartiles
        # outputs3 = example_3_all_quartiles()
        
        # # Example 4: Minimal
        # json4 = example_4_minimal_usage()
        
        # # Example 5: Save/Load
        # data5 = example_5_save_and_load()
        
        # Final summary
        print("\n\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        print("\n✅ All examples completed successfully!")
        
        print("\n📚 Examples:")
        print("   1. File-based usage (most common)")
        print("   2. Text-based usage (API/web apps)")
        print("   3. All quartiles comparison")
        print("   4. Minimal usage (quickest)")
        print("   5. Save/load JSON (persistence)")
        
        print("\n🎯 Key Takeaways:")
        print("   • Use QuartileActionGenerator with your target (Q1/Q2/Q3/Q4)")
        print("   • Feed it keyword metrics and validation results")
        print("   • Get JSON output with all actions")
        print("   • Actions include type, target, current, required, delta, priority")
        
        print("\n💡 Recommended Flow:")
        print("   1. Parse guidelines → GuidelineParser")
        print("   2. Validate article → ImprovedArticleValidator")
        print("   3. Analyze keywords → KeywordQuartileAnalyzer")
        print("   4. Generate actions → QuartileActionGenerator")
        print("   5. Get JSON → output.to_json()")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\n⚠️  Please ensure test files exist:")
        print("   • test_guidelines.txt")
        print("   • test_article.txt")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()