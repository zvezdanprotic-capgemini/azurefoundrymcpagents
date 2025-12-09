"""
Run All MCP Server Integration Tests

Executes all MCP server integration tests and provides a summary.
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
    print("\n" + "🔌" * 35)
    print("  MCP SERVER INTEGRATION TEST SUITE")
    print("🔌" * 35)
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    tests = [
        ("PostgreSQL MCP Server", os.path.join(tests_dir, "test_mcp_postgres_integration.py")),
        ("Azure Blob MCP Server", os.path.join(tests_dir, "test_mcp_blob_integration.py")),
        ("RAG MCP Server", os.path.join(tests_dir, "test_mcp_rag_integration.py")),
        ("Email MCP Server", os.path.join(tests_dir, "test_mcp_email_integration.py")),
    ]
    
    results = {}
    
    for test_name, script_path in tests:
        if os.path.exists(script_path):
            results[test_name] = run_test(test_name, script_path)
        else:
            print(f"\n⚠️  Skipping {test_name}: script not found")
            results[test_name] = None
    
    # Print summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results.items():
        if passed is None:
            status = "⚠️ SKIP"
        elif passed:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        print(f"  {status}  {test_name}")
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 All MCP server integration tests passed!\n")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
