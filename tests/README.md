# IV-Sniper Test Suite

This directory contains all tests for the IV-Sniper trading bot.

## Test Structure

```
tests/
├── README.md                 # This file
├── test_validation.py        # Unit tests for validation utilities
├── test_formatting.py        # Unit tests for formatting utilities
├── test_symbol_utils.py      # Unit tests for symbol utilities
├── test_integration.py       # Integration tests for critical paths
├── test_strike_selector.py   # Existing tests for strike selector
├── test_volume_profile.py    # Existing tests for volume profile
├── test_watchdog.py          # Existing tests for watchdog
└── reset_trade_log.py        # Utility to reset test database
```

## Running Tests

### Run all tests:
```bash
cd tests
python test_validation.py
python test_formatting.py
python test_symbol_utils.py
python test_integration.py
```

### Run specific test file:
```bash
python tests/test_validation.py
```

## Test Coverage

### Unit Tests

#### test_validation.py
Tests for `ui/utils/validation.py`:
- Symbol validation (stock and option symbols)
- Strike price validation
- Quantity and lot size validation
- Premium validation
- Date/expiry validation
- Trade data validation
- Configuration validation
- Numeric range validation

#### test_formatting.py
Tests for `ui/utils/formatting.py`:
- Currency formatting (₹)
- Percentage formatting
- Date/time formatting
- Number formatting
- P&L formatting
- Strike price formatting
- Trade status formatting

#### test_symbol_utils.py
Tests for `ui/utils/symbol_utils.py`:
- Parse Zerodha symbols
- Calculate expiry dates
- Reconstruct option symbols
- Generate trade symbols
- Get all trade symbols

### Integration Tests

#### test_integration.py
End-to-end tests for:
- Database repository operations
- Symbol utilities workflow
- Validation → Formatting pipeline
- Error handling integration
- Complete trade lifecycle

## Test Results

Tests use a simple pass/fail format:
```
✓ Test name (passed)
✗ Test name  Error details (failed)
```

Exit code:
- `0` = All tests passed
- `1` = One or more tests failed

## Adding New Tests

When adding new functionality:
1. Create unit tests in `test_<module>.py`
2. Add integration tests if it affects critical paths
3. Run all tests to ensure no regressions
4. Update this README with new test coverage

## Mock Data

Tests use mock data to avoid dependencies on:
- Live Kite API
- Real market data
- Production database

This ensures tests are fast and reliable.
