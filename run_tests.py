#!/usr/bin/env python3
"""
Test runner script for the Azure AI Foundry KYC Orchestrator
Usage: python run_tests.py [unit|integration|all] [--coverage]
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*50}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False

def install_dependencies():
    """Install test dependencies"""
    print("Installing test dependencies...")
    return run_command([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ], "Installing dependencies")

def run_unit_tests(coverage=False):
    """Run unit tests only"""
    cmd = [sys.executable, "-m", "pytest", "tests/test_main.py", "tests/test_agent_caller.py", "-v"]
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
    
    return run_command(cmd, "Unit tests")

def run_integration_tests():
    """Run integration tests only"""
    print("\n⚠️  Integration tests require:")
    print("   - Valid Azure credentials (AZURE_OPENAI_API_KEY)")
    print("   - Configured Azure AI agents (intake and verification)")
    print("   - Active internet connection")
    
    proceed = input("\nDo you want to proceed with integration tests? (y/N): ")
    if proceed.lower() != 'y':
        print("Skipping integration tests")
        return True
    
    cmd = [sys.executable, "-m", "pytest", "tests/test_integration.py", "-v", "-m", "integration"]
    return run_command(cmd, "Integration tests")

def run_all_tests(coverage=False):
    """Run all tests"""
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
    
    # Skip integration tests if Azure credentials not available
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        cmd.extend(["-m", "not integration"])
        print("\n⚠️  Skipping integration tests (AZURE_OPENAI_API_KEY not found)")
    
    return run_command(cmd, "All tests")

def check_test_environment():
    """Check if test environment is properly set up"""
    print("Checking test environment...")
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ main.py not found. Please run from project root directory.")
        return False
    
    if not Path("agent_caller.py").exists():
        print("❌ agent_caller.py not found. Please run from project root directory.")
        return False
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print(f"❌ Python 3.8+ required, found {python_version.major}.{python_version.minor}")
        return False
    
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    print("✅ Project files found")
    
    return True

def main():
    """Main test runner"""
    if not check_test_environment():
        sys.exit(1)
    
    # Parse command line arguments
    test_type = "unit"  # default
    coverage = False
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    
    if "--coverage" in sys.argv:
        coverage = True
    
    if test_type not in ["unit", "integration", "all"]:
        print("Usage: python run_tests.py [unit|integration|all] [--coverage]")
        sys.exit(1)
    
    success = True
    
    # Install dependencies first
    if not install_dependencies():
        sys.exit(1)
    
    # Run the specified tests
    if test_type == "unit":
        success = run_unit_tests(coverage)
    elif test_type == "integration":
        success = run_integration_tests()
    elif test_type == "all":
        success = run_all_tests(coverage)
    
    # Summary
    print(f"\n{'='*50}")
    if success:
        print("🎉 All tests completed successfully!")
        if coverage and os.path.exists("htmlcov/index.html"):
            print("📊 Coverage report generated: htmlcov/index.html")
    else:
        print("💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()