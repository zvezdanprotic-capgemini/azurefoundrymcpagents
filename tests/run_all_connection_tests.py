"""
Run All Connection Tests
Executes all MCP component connection tests and provides a summary.
"""
import subprocess
import sys
import os

def run_test(test_name: str, script_path: str) -> bool:
    """Run a single test script and return success status."""
    print(f"\n{'=' * 70}")
    print(f"  Running: {test_name}")
    print(f"{'=' * 70}\n")
    
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return result.returncode == 0

def main():
    print("\n" + "🔧" * 35)
    print("  MCP COMPONENT CONNECTION TEST SUITE")
    print("🔧" * 35)
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    tests = [
        ("Azure OpenAI (Chat)", os.path.join(tests_dir, "test_azure_openai_connection.py")),
        ("Azure OpenAI (Embeddings)", os.path.join(tests_dir, "test_azure_embeddings_connection.py")),
        ("PostgreSQL", os.path.join(tests_dir, "test_postgresql_connection.py")),
        ("Azure Blob Storage", os.path.join(tests_dir, "test_azure_blob_connection.py")),
        ("SendGrid Email", os.path.join(tests_dir, "test_sendgrid_connection.py")),
    ]
    
    results = {}
    
    for test_name, script_path in tests:
        results[test_name] = run_test(test_name, script_path)
    
    # Print summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 All connection tests passed!\n")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
