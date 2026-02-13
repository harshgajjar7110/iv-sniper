# Deprecation Warnings Fix Plan

## Summary

This plan addresses two types of deprecation warnings in the UI code:

1. **`Styler.applymap` deprecation** - Pandas has deprecated `applymap` in favor of `map`
2. **`use_container_width` deprecation** - Streamlit has deprecated this parameter in favor of `width`

---

## Issue 1: Styler.applymap Deprecation

### Location
- [`position_monitor.py`](ui/pages/position_monitor.py) - 2 occurrences

### Details
| Line | Current Code | Fixed Code |
|------|--------------|------------|
| 384 | `df.style.applymap(color_pnl, subset=pnl_columns)` | `df.style.map(color_pnl, subset=pnl_columns)` |
| 452 | `summary_df.style.applymap(color_pnl, subset=[...])` | `summary_df.style.map(color_pnl, subset=[...])` |

### Fix
Replace `applymap` with `map` - the API is identical, just the method name has changed.

---

## Issue 2: use_container_width Deprecation

### Locations
5 files with 14 total occurrences:

#### [`position_monitor.py`](ui/pages/position_monitor.py) - 4 occurrences
| Line | Component | Current | Fixed |
|------|-----------|---------|-------|
| 126 | `st.button` | `use_container_width=True` | `width="stretch"` |
| 138 | `st.button` | `use_container_width=True` | `width="stretch"` |
| 399 | `st.dataframe` | `use_container_width=True` | `width="stretch"` |
| 465 | `st.dataframe` | `use_container_width=True` | `width="stretch"` |

#### [`trade_execution.py`](ui/pages/trade_execution.py) - 3 occurrences
| Line | Component | Current | Fixed |
|------|-----------|---------|-------|
| 78 | `st.plotly_chart` | `use_container_width=True` | `width="stretch"` |
| 264 | `st.button` | `use_container_width=True` | `width="stretch"` |
| 300 | `st.button` | `use_container_width=True` | `width="stretch"` |

#### [`scanner.py`](ui/pages/scanner.py) - 3 occurrences
| Line | Component | Current | Fixed |
|------|-----------|---------|-------|
| 61 | `st.button` | `use_container_width=True` | `width="stretch"` |
| 205 | `st.plotly_chart` | `use_container_width=True` | `width="stretch"` |
| 212 | `st.button` | `use_container_width=True` | `width="stretch"` |

#### [`dashboard.py`](ui/pages/dashboard.py) - 2 occurrences
| Line | Component | Current | Fixed |
|------|-----------|---------|-------|
| 39 | `st.button` | `use_container_width=True` | `width="stretch"` |
| 247 | `st.dataframe` | `use_container_width=True` | `width="stretch"` |

#### [`configuration.py`](ui/pages/configuration.py) - 2 occurrences
| Line | Component | Current | Fixed |
|------|-----------|---------|-------|
| 223 | `st.button` | `use_container_width=True` | `width="stretch"` |
| 235 | `st.button` | `use_container_width=True` | `width="stretch"` |

### Fix
Replace `use_container_width=True` with `width="stretch"` for all occurrences.
Note: All current usages are `use_container_width=True`, so we consistently use `width="stretch"`.

---

## Implementation Order

1. Fix `position_monitor.py` - both applymap and use_container_width issues
2. Fix `trade_execution.py` - use_container_width issues
3. Fix `scanner.py` - use_container_width issues
4. Fix `dashboard.py` - use_container_width issues
5. Fix `configuration.py` - use_container_width issues

---

## Testing

After making changes:
1. Run the Streamlit app
2. Navigate to each page that was modified
3. Verify no deprecation warnings appear in the console
4. Verify UI renders correctly with the new parameter
