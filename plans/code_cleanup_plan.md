# IV-Sniper Code Cleanup & Issue Fixes Plan

## Executive Summary

This document outlines a comprehensive code cleanup and issue resolution plan for the IV-Sniper trading bot. The analysis identified multiple categories of issues ranging from critical bugs to code quality improvements.

---

## 🔴 Critical Issues (High Priority)

### 1. Incomplete TODO Implementations

**Location:** Multiple UI pages
**Impact:** Features appear functional but don't execute actual operations

#### Issues Found:
- [`ui/pages/trade_execution.py:229`](ui/pages/trade_execution.py:229) - Market order placement not implemented
- [`ui/pages/trade_execution.py:241`](ui/pages/trade_execution.py:241) - Limit order placement not implemented
- [`ui/pages/dashboard.py:40`](ui/pages/dashboard.py:40) - Emergency stop logic not implemented
- [`ui/pages/configuration.py:53`](ui/pages/configuration.py:53) - Settings save functionality not implemented
- [`ui/pages/configuration.py:92`](ui/pages/configuration.py:92) - Scanner settings save not implemented
- [`ui/pages/configuration.py:139`](ui/pages/configuration.py:139) - Exit rules save not implemented
- [`ui/pages/configuration.py:175`](ui/pages/configuration.py:175) - Kill switch logic not implemented

**Recommended Actions:**
1. Implement actual order placement logic in trade execution page
2. Create configuration persistence layer (database or config file)
3. Implement emergency stop and kill switch functionality
4. Add proper error handling and validation for all operations

---

### 2. Bare Exception Handling

**Location:** Throughout codebase (60+ instances)
**Impact:** Masks errors, makes debugging difficult, potential silent failures

#### Critical Instances:
- [`ui/utils/data_utils.py:220`](ui/utils/data_utils.py:220) - Bare except for date parsing
- [`ui/utils/data_utils.py:523`](ui/utils/data_utils.py:523) - Bare except for date parsing
- [`ui/pages/dashboard.py:67`](ui/pages/dashboard.py:67) - Bare except for margin fetching
- [`ui/pages/position_monitor.py:538`](ui/pages/position_monitor.py:538) - Bare except for date parsing

**Recommended Actions:**
1. Replace all bare `except:` with specific exception types
2. Add proper logging for all caught exceptions
3. Implement fallback values with clear documentation
4. Use `except Exception as e:` at minimum for broad catches

**Example Fix:**
```python
# Before
try:
    expiry = date(year, month_num, last_day)
except:
    expiry = date.today()

# After
try:
    expiry = date(year, month_num, last_day)
except (ValueError, TypeError) as e:
    logger.warning(f"Invalid date components for expiry calculation: {e}")
    expiry = date.today()
```

---

### 3. Incomplete Error Recovery in Order Manager

**Location:** [`executor/order_manager.py:94`](executor/order_manager.py:94)
**Impact:** Potential naked positions if short leg fails after long leg succeeds

**Issue:**
```python
except Exception as e:
    logger.error(f"Live order placement failed: {e}")
    # TODO: If long placed but short failed, we have a naked buy.
    # Should reverse long? For now, just log error.
```

**Recommended Actions:**
1. Implement order rollback mechanism
2. Track partial order states in database
3. Add manual intervention alerts for failed spreads
4. Implement automatic position reconciliation

---

## 🟡 Code Quality Issues (Medium Priority)

### 4. Duplicate Code - Symbol Reconstruction Logic

**Location:** Multiple files
**Impact:** Maintenance burden, inconsistency risk

#### Duplicate Instances:
- [`ui/utils/data_utils.py:526-531`](ui/utils/data_utils.py:526) - Symbol reconstruction in `calculate_spread_pnl()`
- [`ui/pages/position_monitor.py:537-551`](ui/pages/position_monitor.py:537) - Symbol reconstruction in position monitor
- [`watchdog/monitor.py:42-59`](watchdog/monitor.py:42) - Symbol reconstruction in watchdog
- [`ui/pages/dashboard.py:160-172`](ui/pages/dashboard.py:160) - Symbol reconstruction in dashboard

**Recommended Actions:**
1. Create centralized utility function for symbol reconstruction
2. Add comprehensive unit tests for symbol parsing
3. Refactor all instances to use the centralized function

**Proposed Solution:**
```python
# In ui/utils/data_utils.py or new utils/symbol_utils.py
def reconstruct_option_symbol(
    symbol: str,
    expiry: str,
    strike: int,
    strategy: str,
    include_exchange: bool = True
) -> str:
    """
    Reconstruct Zerodha option trading symbol from components.
    
    Args:
        symbol: Underlying symbol (e.g., 'NIFTY', 'RELIANCE')
        expiry: Expiry date in YYYY-MM-DD format
        strike: Strike price
        strategy: Strategy type (BULL_PUT or BEAR_CALL)
        include_exchange: Whether to prefix with 'NFO:'
    
    Returns:
        Trading symbol (e.g., 'NFO:NIFTY24FEB21500CE')
    """
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid expiry format '{expiry}': {e}")
        raise ValueError(f"Invalid expiry format: {expiry}")
    
    yy = str(exp_date.year)[-2:]
    mon = exp_date.strftime("%b").upper()
    leg_type = "PE" if "PUT" in strategy else "CE"
    
    trading_symbol = f"{symbol}{yy}{mon}{int(strike)}{leg_type}"
    
    if include_exchange:
        return f"NFO:{trading_symbol}"
    return trading_symbol
```

---

### 5. Inconsistent Error Logging

**Location:** Throughout codebase
**Impact:** Difficult debugging, inconsistent log messages

**Issues:**
- Mix of f-strings and % formatting in log messages
- Inconsistent error message formats
- Some exceptions logged, others not
- Missing context in error messages

**Recommended Actions:**
1. Standardize on f-string formatting for all log messages
2. Create logging guidelines document
3. Add contextual information to all error logs
4. Implement structured logging for critical operations

---

### 6. Missing Type Hints

**Location:** Various functions
**Impact:** Reduced code clarity, harder to maintain

**Examples:**
- [`ui/pages/position_monitor.py:43`](ui/pages/position_monitor.py:43) - `render_position_card()` missing return type
- [`ui/pages/position_monitor.py:144`](ui/pages/position_monitor.py:144) - `render_live_position_card()` missing return type
- Several utility functions missing parameter types

**Recommended Actions:**
1. Add type hints to all public functions
2. Use `typing` module for complex types
3. Consider using `mypy` for type checking
4. Add return type hints (including `None` where applicable)

---

### 7. Hardcoded Values

**Location:** Multiple files
**Impact:** Difficult to configure, testing challenges

**Examples:**
- [`ui/utils/data_utils.py:117`](ui/utils/data_utils.py:117) - Hardcoded capital value `1_000_000`
- [`scanner/scanner.py:46`](scanner/scanner.py:46) - Hardcoded `MAX_CANDIDATES = 5`
- Magic numbers in calculations without explanation

**Recommended Actions:**
1. Move all hardcoded values to [`config.py`](config.py)
2. Add configuration documentation
3. Implement configuration validation
4. Consider environment-specific configs

---

## 🟢 Code Improvements (Low Priority)

### 8. Debug Logging Artifacts

**Location:** [`ui/pages/scanner.py:234-236`](ui/pages/scanner.py:234)
**Impact:** Clutters logs, should be removed or made conditional

**Issue:**
```python
logger.info("DEBUG: Initialized scan_logs to empty list")
logger.info(f"DEBUG: scan_logs already exists, length={len(st.session_state.scan_logs)}")
```

**Recommended Actions:**
1. Remove debug logging or make it conditional on debug flag
2. Use proper logging levels (DEBUG vs INFO)
3. Clean up development artifacts

---

### 9. Inconsistent Function Naming

**Location:** Various modules
**Impact:** Reduced code readability

**Examples:**
- Mix of `get_*` and `fetch_*` prefixes for similar operations
- Some functions use verbs, others use nouns
- Inconsistent naming patterns across modules

**Recommended Actions:**
1. Establish naming conventions document
2. Standardize function prefixes:
   - `get_*` for database queries
   - `fetch_*` for API calls
   - `calculate_*` for computations
   - `validate_*` for validation functions

---

### 10. Missing Docstrings

**Location:** Various functions
**Impact:** Reduced code maintainability

**Recommended Actions:**
1. Add docstrings to all public functions
2. Use consistent docstring format (Google or NumPy style)
3. Include parameter descriptions and return types
4. Add usage examples for complex functions

---

## 📊 Code Metrics & Statistics

### Current State:
- **Total Python Files:** 40+
- **TODO Comments:** 7 critical items
- **Bare Exceptions:** 60+ instances
- **Duplicate Code Blocks:** 4+ major instances
- **Missing Type Hints:** ~30% of functions
- **Lines of Code:** ~5,000+

---

## 🔧 Refactoring Opportunities

### 11. Extract Common Utilities

**Recommended New Modules:**

#### `utils/symbol_utils.py`
- Symbol parsing and reconstruction
- Expiry date calculations
- Strike price formatting

#### `utils/validation.py`
- Input validation functions
- Data sanitization
- Type checking utilities

#### `utils/formatting.py`
- Currency formatting
- Date/time formatting
- Display string generation

---

### 12. Improve Database Layer

**Current Issues:**
- Direct SQL in multiple places
- No query builder abstraction
- Limited error handling

**Recommended Actions:**
1. Create repository pattern for database access
2. Add query builders for common operations
3. Implement connection pooling
4. Add database migration system

---

### 13. Enhance Testing Infrastructure

**Current State:**
- Limited test coverage
- Tests in `/tests` directory but not comprehensive

**Recommended Actions:**
1. Add unit tests for all utility functions
2. Create integration tests for critical paths
3. Add mock data generators for testing
4. Implement CI/CD pipeline with automated testing

---

## 🎯 Implementation Priority Matrix

### Phase 1: Critical Fixes (Week 1-2)
1. ✅ Fix bare exception handling in critical paths
2. ✅ Implement order rollback mechanism
3. ✅ Complete TODO implementations for order placement
4. ✅ Add proper error logging throughout

### Phase 2: Code Quality (Week 3-4)
1. ✅ Extract duplicate symbol reconstruction logic
2. ✅ Standardize error handling patterns
3. ✅ Add type hints to public APIs
4. ✅ Move hardcoded values to config

### Phase 3: Refactoring (Week 5-6)
1. ✅ Create utility modules
2. ✅ Improve database layer
3. ✅ Add comprehensive docstrings
4. ✅ Standardize naming conventions

### Phase 4: Testing & Documentation (Week 7-8)
1. ✅ Add unit tests
2. ✅ Create integration tests
3. ✅ Update documentation
4. ✅ Code review and cleanup

---

## 📝 Specific Code Changes Needed

### File: [`ui/utils/data_utils.py`](ui/utils/data_utils.py)

#### Change 1: Fix bare exception handling
**Lines:** 220-221, 523-524

```python
# Current
except:
    expiry = date.today()

# Proposed
except (ValueError, TypeError) as e:
    logger.warning(f"Date parsing failed: {e}. Using today's date as fallback.")
    expiry = date.today()
```

#### Change 2: Extract symbol reconstruction
**Lines:** 526-531

```python
# Current - inline reconstruction
yy = str(exp_date.year)[-2:]
mon = exp_date.strftime("%b").upper()
leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"

# Proposed - use utility function
short_sym = reconstruct_option_symbol(
    symbol=trade['symbol'],
    expiry=trade['expiry'],
    strike=trade['short_strike'],
    strategy=trade['strategy'],
    include_exchange=True
)
```

#### Change 3: Remove hardcoded capital
**Lines:** 117

```python
# Current
return {
    'total_capital': 1_000_000,
    'used_margin': 0,
    'available': 1_000_000,
}

# Proposed
return {
    'total_capital': config.TOTAL_CAPITAL,
    'used_margin': 0,
    'available': config.TOTAL_CAPITAL,
}
```

---

### File: [`executor/order_manager.py`](executor/order_manager.py)

#### Change 1: Implement order rollback
**Lines:** 92-95

```python
# Current
except Exception as e:
    logger.error(f"Live order placement failed: {e}")
    # TODO: If long placed but short failed, we have a naked buy.

# Proposed
except Exception as e:
    logger.error(f"Live order placement failed: {e}")
    
    # Rollback long leg if it was placed
    if long_order_id:
        try:
            logger.warning(f"Attempting to cancel long leg order: {long_order_id}")
            self.kite.cancel_order(long_order_id)
            logger.info(f"Successfully cancelled long leg order: {long_order_id}")
        except Exception as cancel_error:
            logger.critical(
                f"CRITICAL: Failed to cancel long leg {long_order_id}. "
                f"Manual intervention required. Error: {cancel_error}"
            )
            # Send alert notification
            self._send_critical_alert(
                f"Naked position alert: {symbol} long leg {long_order_id}"
            )
    
    return False
```

---

### File: [`ui/pages/trade_execution.py`](ui/pages/trade_execution.py)

#### Change 1: Implement market order placement
**Lines:** 228-230

```python
# Current
if market_btn:
    # TODO: Implement actual order placement
    st.success("✅ Market order placed successfully!")

# Proposed
if market_btn:
    try:
        kite = get_kite_client()
        order_manager = OrderManager(kite)
        
        # Validate spread data
        if not spread_data or 'short_symbol' not in spread_data:
            st.error("❌ Invalid spread data. Please analyze again.")
            return
        
        # Place the spread order
        success = order_manager.place_spread_order(
            symbol=st.session_state.get('selected_symbol'),
            spread=spread_data
        )
        
        if success:
            st.success("✅ Market order placed successfully!")
            st.rerun()
        else:
            st.error("❌ Order placement failed. Check logs for details.")
            
    except Exception as e:
        logger.error(f"Market order placement error: {e}")
        st.error(f"❌ Order placement failed: {str(e)}")
```

---

### File: [`ui/pages/configuration.py`](ui/pages/configuration.py)

#### Change 1: Implement settings persistence
**Lines:** 52-54

```python
# Current
if st.button("💾 Save General Settings", type="primary"):
    # TODO: Save to config or database
    st.success("✅ General settings saved!")

# Proposed
if st.button("💾 Save General Settings", type="primary"):
    try:
        # Save to database
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO config_settings 
                (key, value, updated_at) 
                VALUES 
                ('paper_trade_mode', ?, datetime('now')),
                ('max_open_trades', ?, datetime('now')),
                ('min_capital_required', ?, datetime('now'))
            """, (
                str(paper_trade_mode),
                str(max_open_trades),
                str(min_capital_required)
            ))
        
        # Update runtime config
        config.PAPER_TRADE_MODE = paper_trade_mode
        config.MAX_OPEN_TRADES = max_open_trades
        config.MIN_CAPITAL_REQUIRED = min_capital_required
        
        st.success("✅ General settings saved successfully!")
        logger.info("Configuration updated by user")
        
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        st.error(f"❌ Failed to save settings: {str(e)}")
```

---

## 🔍 Testing Strategy

### Unit Tests Needed:

1. **Symbol Utilities**
   - Test symbol parsing with valid inputs
   - Test symbol parsing with invalid inputs
   - Test symbol reconstruction
   - Test edge cases (leap years, month boundaries)

2. **Data Utilities**
   - Test P&L calculations
   - Test exit status logic
   - Test position grouping
   - Test quote fetching with mocked API

3. **Order Management**
   - Test order placement logic
   - Test rollback mechanism
   - Test error handling
   - Test state transitions

### Integration Tests Needed:

1. **Scanner → Analyst → Executor Pipeline**
2. **Watchdog Monitoring Loop**
3. **UI → Backend Communication**
4. **Database Operations**

---

## 📚 Documentation Improvements

### 1. Add Architecture Diagram
Create Mermaid diagram showing system components and data flow

### 2. API Documentation
Document all public functions with examples

### 3. Configuration Guide
Comprehensive guide for all config parameters

### 4. Deployment Guide
Step-by-step deployment instructions

### 5. Troubleshooting Guide
Common issues and solutions

---

## 🚀 Migration Path

### Step-by-Step Implementation:

1. **Create feature branch:** `feature/code-cleanup`
2. **Implement Phase 1 fixes** (critical issues)
3. **Run existing tests** to ensure no regressions
4. **Code review** with team
5. **Merge to develop branch**
6. **Repeat for Phases 2-4**

### Rollback Strategy:

- Keep original code commented for reference
- Tag each phase completion in git
- Maintain detailed changelog
- Test thoroughly before each merge

---

## 📈 Success Metrics

### Code Quality Metrics:
- ✅ Zero bare `except:` statements
- ✅ 100% of TODOs resolved or tracked
- ✅ 90%+ type hint coverage
- ✅ 80%+ test coverage
- ✅ Zero critical security issues

### Performance Metrics:
- ✅ No performance degradation
- ✅ Improved error recovery time
- ✅ Reduced log noise

### Maintainability Metrics:
- ✅ Reduced code duplication by 50%+
- ✅ Improved documentation coverage
- ✅ Standardized coding patterns

---

## 🎓 Best Practices to Adopt

### 1. Error Handling
- Always use specific exception types
- Log all exceptions with context
- Implement proper fallback mechanisms
- Never silently fail

### 2. Code Organization
- One responsibility per function
- Extract common logic to utilities
- Keep functions under 50 lines
- Use meaningful variable names

### 3. Configuration Management
- All configurable values in config.py
- Environment-specific overrides
- Validation on startup
- Documentation for each parameter

### 4. Logging
- Use appropriate log levels
- Include contextual information
- Structured logging for critical operations
- Regular log rotation

### 5. Testing
- Write tests before fixing bugs
- Test edge cases
- Mock external dependencies
- Maintain test data fixtures

---

## 🔗 Related Documents

- [`PRD.md`](PRD.md) - Product Requirements
- [`UI.md`](UI.md) - UI Specifications
- [`GEMINI.md`](GEMINI.md) - AI Integration Guide
- [`requirements.txt`](requirements.txt) - Dependencies

---

## 📞 Questions & Clarifications Needed

1. **Configuration Persistence:** Should settings be saved to database or config file?
2. **Order Rollback:** What's the acceptable timeout for rollback attempts?
3. **Alert System:** Should we implement email/SMS alerts for critical errors?
4. **Testing Environment:** Do we have a paper trading environment for testing?
5. **Deployment Schedule:** When can we schedule downtime for major refactoring?

---

## 🎯 Next Steps

1. Review this plan with the team
2. Prioritize issues based on business impact
3. Assign owners for each phase
4. Set up tracking in project management tool
5. Schedule kickoff meeting for Phase 1

---

**Document Version:** 1.0  
**Created:** 2026-02-13  
**Last Updated:** 2026-02-13  
**Author:** Code Architect  
**Status:** Draft - Awaiting Review
