# Documentation Archive

This directory contains detailed documentation files that provide in-depth information about the VANET system.

## 📑 Index

### 🛠️ Setup & Installation
- **new_developer_setup.sh** - Complete setup script for new developers
- **setup_phase1.sh** - Phase 1 setup (SUMO + basic simulation)
- **setup_rl.sh** - RL module setup
- **setup_ns3_integration.sh** - NS3 integration setup

### 🚀 Quick References
- **COMMANDS.md** - Complete command reference with all options and examples
- **QUICK_START.md** - Getting started guide for new users
- **QUICK_REFERENCE.md** - Quick lookup for common commands
- **QUICK_FIX_SUMMARY.md** - Summary of quick fixes applied

### 🔧 Bug Fixes & Solutions
- **FIXES_EXPLAINED.md** - Detailed explanation of all fixes (Nov 1, 2025)
  - Security message confusion fix
  - Rule-based mode stopping immediately fix
  - All 4 mode combinations tested
- **SYSTEM_FIXED.md** - Summary of system fixes
- **ALL_ERRORS_FIXED.md** - Historical error fixes
- **FIXED_ISSUES.md** - Compilation and runtime issue fixes
- **SUMO_TROUBLESHOOTING.md** - SUMO-specific troubleshooting

### 📊 System Status & Progress
- **WORKING_SYSTEM.md** - Current working system status
- **SYSTEM_COMPLETE.md** - System completion documentation
- **PHASE1_COMPLETE.md** - Phase 1 completion status
- **INTEGRATION_SUMMARY.md** - Integration summary and results

### 🔐 Security Documentation
- **SECURITY_WORKING.md** - How security system works (TraCI timeout fix)
- **SECURITY_README.md** - Security features overview
- **SECURITY_INTEGRATION_GUIDE.md** - Security integration guide
- **V2V_SECURITY_README.md** - V2V security implementation
- **OUTPUT_EXPLAINED.md** - Understanding security-related output messages

### 🤖 Reinforcement Learning
- **RL_GUIDE.md** - RL system guide
- **RL_SYSTEM_GUIDE.md** - Detailed RL implementation guide
- **README_RL_FIXES.md** - RL module fixes

### 📜 Legacy Documentation
- **README_OLD.md** - Previous README versions
- **README_old.md** - Historical README

---

## 🔍 Finding What You Need

### For New Users
Start with:
1. **QUICK_START.md** - Get up and running
2. **COMMANDS.md** - Learn available commands
3. Main **README.md** (in root) - Comprehensive guide

### For Troubleshooting
Check:
1. **FIXES_EXPLAINED.md** - Recent fixes and solutions
2. **OUTPUT_EXPLAINED.md** - Understanding error messages
3. **SUMO_TROUBLESHOOTING.md** - SUMO-specific issues

### For Development
Review:
1. **WORKING_SYSTEM.md** - Current system architecture
2. **INTEGRATION_SUMMARY.md** - How components integrate
3. **SECURITY_INTEGRATION_GUIDE.md** - Adding security features
4. **RL_GUIDE.md** - Working with RL module

### For Security Features
See:
1. **SECURITY_WORKING.md** - Security system explanation
2. **V2V_SECURITY_README.md** - V2V encryption details
3. **OUTPUT_EXPLAINED.md** - Security message flow

---

## 📝 Most Recent Updates (Nov 1, 2025)

### FIXES_EXPLAINED.md
**What it covers:**
- Security message confusion (Enabled → Disabled → Enabled)
- Rule-based mode stopping immediately
- Vehicle check timing fix
- All 4 mode combinations (Rule/RL × Security/No-Security)
- Testing results and verification

**When to read:** If you see confusing security messages or simulation stops early.

### SYSTEM_FIXED.md
**What it covers:**
- Summary of both fixes
- Quick comparison (Before/After)
- Testing results table
- How to use all modes

**When to read:** Quick overview of recent fixes.

### OUTPUT_EXPLAINED.md
**What it covers:**
- Why "Enabled" then "Disabled" appeared
- Initialization flow timing
- Simple and technical explanations
- Security startup process

**When to read:** Want to understand system output messages.

---

## 🎯 Quick Navigation

**Want to...**
- **Run the system?** → See main README.md or QUICK_START.md
- **Understand commands?** → COMMANDS.md
- **Fix an issue?** → FIXES_EXPLAINED.md
- **Learn about security?** → SECURITY_WORKING.md
- **Work with RL?** → RL_GUIDE.md
- **Integrate features?** → INTEGRATION_SUMMARY.md

---

## 📞 Documentation Hierarchy

```
README.md (root)                    ← Start here
├── Quick Start Guide
├── Installation
├── Usage Examples
└── Troubleshooting

docs/archive/                       ← Detailed information
├── COMMANDS.md                     ← Command reference
├── QUICK_START.md                  ← Step-by-step guide
├── FIXES_EXPLAINED.md              ← Bug fixes (LATEST)
├── OUTPUT_EXPLAINED.md             ← Output interpretation (LATEST)
├── SECURITY_WORKING.md             ← Security details
├── RL_GUIDE.md                     ← RL implementation
└── ... other detailed docs
```

---

**Last Updated**: November 1, 2025
**Total Documents**: 23 files
**Most Recent**: FIXES_EXPLAINED.md, SYSTEM_FIXED.md, OUTPUT_EXPLAINED.md

For the latest comprehensive guide, always refer to the main **README.md** in the root directory.
