# Testing Documentation

## Overview

The Azure AI Foundry KYC Orchestrator includes comprehensive testing to ensure reliability and correctness of both unit-level functions and integration with Azure AI agents.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── test_agent_config.py        # Agent configuration validation
├── test_agent_caller.py        # Unit tests for Azure AI integration
├── test_main.py                # Unit tests for FastAPI application
└── test_integration.py         # Integration tests with real agents
```

## Test Categories

### 1. Unit Tests
- **test_agent_config.py**: Validates agent configuration and IDs
- **test_agent_caller.py**: Tests Azure AI Projects SDK integration logic
- **test_main.py**: Tests FastAPI application endpoints and workflow logic

### 2. Integration Tests
- **test_integration.py**: Tests actual Azure AI agents with real API calls
- Requires valid Azure credentials and active agent endpoints
- Tests both intake and verification agents (the implemented ones)

## Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Ensure Azure credentials are configured
export AZURE_OPENAI_API_KEY="your-key"
```

### Test Commands

```bash
# Run all unit tests
python -m pytest tests/test_*.py -v -m "not integration"

# Run integration tests (requires Azure credentials)
python -m pytest tests/test_integration.py -v -m integration

# Run all tests with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Use the test runner script
python run_tests.py unit           # Unit tests only
python run_tests.py integration    # Integration tests only  
python run_tests.py all            # All tests
python run_tests.py all --coverage # All tests with coverage
```

## Test Results Summary

### ✅ Agent Configuration Tests
- Validates that intake and verification agents have correct IDs
- Confirms unconfigured agents (eligibility, recommendation, compliance, action) are set to None
- Verifies agent ID format and structure

### ✅ Unit Test Coverage
- **FastAPI Endpoints**: Session creation, workflow steps, health checks
- **Agent Calling Logic**: Retry mechanisms, error handling, response parsing
- **Workflow Logic**: JSON detection, PASS validation, step progression
- **Authentication**: Azure credential handling and fallback logic

### ✅ Integration Test Results
```
Agent Connectivity:
  ✅ intake: Available (asst_ubknxDV1JTZ4QOTNJIwyTCGO)
  ✅ verification: Available (asst_DQY27aSL6P4yfYvnVUfhWnti) 
  ⏸️ eligibility: Not configured
  ⏸️ recommendation: Not configured
  ⏸️ compliance: Not configured
  ⏸️ action: Not configured
```

### ✅ Real Agent Testing
- **Intake Agent**: Successfully processes customer data and requests additional information
- **Verification Agent**: Provides structured responses for KYC verification
- **Authentication**: DefaultAzureCredential working correctly
- **Thread Management**: Each agent call creates unique conversation threads

## Test Features

### Insurance Employee Workflow Testing
- Tests the new workflow where agents can have multiple conversations
- Validates JSON response detection and PASS criteria checking
- Confirms non-JSON responses continue conversations appropriately

### Error Handling Testing
- Network failures and retry logic
- Invalid agent IDs and missing configurations
- Authentication failures and credential fallbacks
- Malformed responses and timeout scenarios

### Performance Testing
- Agent response times and thread creation
- Session management and memory usage
- Concurrent request handling

## CI/CD Integration

The test suite is designed for integration with CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Unit Tests
  run: python run_tests.py unit

- name: Run Integration Tests  
  run: python run_tests.py integration
  env:
    AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}
```

## Test Data and Mocking

### Unit Tests
- Use extensive mocking to isolate components
- Mock Azure AI Projects SDK responses
- Test edge cases and error conditions

### Integration Tests  
- Use real Azure AI agents with actual API calls
- Sanitized test data that doesn't contain real customer information
- Automatic cleanup of test sessions and threads

## Monitoring and Alerts

Tests include validation for:
- Agent availability and response times
- API quota usage and rate limiting
- Authentication token expiration
- Service health and degradation

## Future Test Enhancements

### Additional Test Coverage
- **Frontend Component Tests**: React component testing with Jest
- **End-to-End Tests**: Full user workflow automation with Playwright
- **Load Testing**: Performance testing with multiple concurrent sessions
- **Security Testing**: Authentication and authorization validation

### Agent Expansion Testing
- Tests for eligibility, recommendation, compliance, and action agents
- Multi-agent workflow testing and handoff validation
- Complex business logic testing with real-world scenarios

## Troubleshooting

### Common Issues
1. **Integration Test Failures**: Check Azure credentials and agent availability
2. **Import Errors**: Ensure virtual environment is activated and dependencies installed
3. **Async Test Issues**: Verify pytest-asyncio is installed and configured

### Debug Commands
```bash
# Check agent connectivity
python -c "import asyncio; from agent_caller import test_agent_connection; print(asyncio.run(test_agent_connection()))"

# Test specific agent
python -c "import asyncio; from agent_caller import call_azure_ai_agent; print(asyncio.run(call_azure_ai_agent('intake', {'session_id': 'test', 'data': {'name': 'Test'}})))"

# Validate configuration
python -m pytest tests/test_agent_config.py -v
```