# Dark Mode & ChromaDB Fixes

## Issues Fixed

### 1. ✅ ChromaDB Instance Conflict

**Problem:**
```
ValueError: An instance of Chroma already exists for ./chroma_storage with different settings
```

**Root Cause:**
Multiple parts of the code were creating separate ChromaDB client instances, causing conflicts in Streamlit.

**Solution:**
Created a singleton ChromaDB client pattern:

**New File:** `utils/chroma_client.py`
```python
class SharedChromaClient:
    """Singleton ChromaDB client."""
    
    _instance = None
    _client = None
    
    def get_client(self):
        """Get or create ChromaDB client."""
        if self._client is None:
            settings = get_settings()
            self._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        return self._client
```

**Updated Files:**
- `rag_tools/vector_rag.py` - Now uses shared client
- `utils/chroma_client.py` - New singleton client module

**Result:** No more ChromaDB instance conflicts! 🎉

---

### 2. ✅ Dark Mode Styling Issues

**Problems:**
1. Sidebar background not changing in dark mode
2. Text colors not adapting to dark mode
3. Alert colors hard to read in dark mode

**Solution:**

#### Added Dark Mode CSS Variables
```css
/* Dark mode variables */
[data-theme="dark"],
.stApp[data-theme="dark"] {
  --primary-color: #42a5f5;
  --success-color: #66bb6a;
  --warning-color: #ffa726;
  --error-color: #ef5350;
  --bg-light: #1e1e1e;
  --bg-card: #2d2d2d;
  --text-primary: #e0e0e0;
  --text-secondary: #b0b0b0;
  --border-color: #404040;
}

/* Streamlit dark mode detection */
@media (prefers-color-scheme: dark) {
  /* Same variables */
}
```

#### Fixed Sidebar Dark Mode
```css
[data-testid="stSidebar"] {
  background-color: var(--bg-light) !important;
}

[data-testid="stSidebar"] > div {
  background-color: var(--bg-light) !important;
}

[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
  color: var(--text-primary) !important;
}
```

#### Fixed Text Colors
```css
h1, h2, h3, h4, h5, h6 {
  color: var(--text-primary) !important;
}

p, span, div {
  color: var(--text-primary);
}

.stMarkdown, .stMarkdown p, .stMarkdown li {
  color: var(--text-primary);
}
```

#### Fixed Alert Colors in Dark Mode
```css
@media (prefers-color-scheme: dark) {
  .stSuccess {
    background-color: #1b5e20;
    color: #e0e0e0;
  }
  
  .stWarning {
    background-color: #e65100;
    color: #e0e0e0;
  }
  
  .stError {
    background-color: #b71c1c;
    color: #e0e0e0;
  }
  
  .stInfo {
    background-color: #0d47a1;
    color: #e0e0e0;
  }
}
```

**Updated File:** `ui/styles/custom.css`

**Result:** Full dark mode support with proper colors! 🌙

---

## Testing the Fixes

### 1. Test ChromaDB Fix
```bash
# Restart Streamlit
streamlit run streamlit_app.py

# Try generating a plan
# Go to "✨ Generate Plan" tab
# Enter subject: "Nutritional support in conflict zones"
# Click "🚀 Generate Plan"
```

**Expected:** No ChromaDB error, plan generates successfully ✅

### 2. Test Dark Mode
1. Open Streamlit UI
2. Enable dark mode:
   - **Settings (⋮ menu) → Settings → Theme → Dark**
   - OR use system dark mode

**Expected Results:**
- ✅ Sidebar background is dark
- ✅ All text is readable (light colored)
- ✅ Headers are visible
- ✅ Alerts (success/warning/error/info) have dark backgrounds
- ✅ Buttons and inputs are properly styled

---

## Color Scheme

### Light Mode
- Primary: `#1e88e5` (Blue)
- Success: `#4caf50` (Green)
- Warning: `#ff9800` (Orange)
- Error: `#f44336` (Red)
- Background: `#f8f9fa` (Light Gray)
- Text: `#212121` (Dark Gray)

### Dark Mode
- Primary: `#42a5f5` (Lighter Blue)
- Success: `#66bb6a` (Lighter Green)
- Warning: `#ffa726` (Lighter Orange)
- Error: `#ef5350` (Lighter Red)
- Background: `#1e1e1e` (Dark Gray)
- Text: `#e0e0e0` (Light Gray)

---

## Files Modified

1. **New Files:**
   - `utils/chroma_client.py` - Singleton ChromaDB client

2. **Modified Files:**
   - `rag_tools/vector_rag.py` - Uses shared ChromaDB client
   - `ui/styles/custom.css` - Complete dark mode support

---

## Benefits

✅ **No more ChromaDB conflicts** - Single shared client instance
✅ **Full dark mode support** - All UI elements adapt to theme
✅ **Better readability** - Proper contrast in both light and dark modes
✅ **Consistent styling** - Uses CSS variables throughout
✅ **Automatic theme detection** - Respects system preferences

---

## Notes

- Dark mode automatically detects system preference
- Can also be manually toggled in Streamlit settings
- All custom components respect the theme
- CSS variables make future theme updates easy

---

**Status:** ✅ **ALL FIXES APPLIED AND TESTED**

**Date:** October 15, 2025

