# Stratum — AI Trading Strategy Analyzer

## Installation Guide

© 2025 Woven Model | support: jude@wovenmodel.com

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Operating System** | Windows 10 64-bit | Windows 11 64-bit |
| **Processor** | Intel Core i3 / AMD Ryzen 3 (or equivalent) | Intel Core i5 / AMD Ryzen 5 |
| **RAM** | 4 GB | 8 GB or more |
| **Disk Space** | 500 MB free | 1 GB free |
| **Display** | 1366 × 768 | 1920 × 1080 or higher |
| **Internet** | Required for first-time activation | Required for updates and data feeds |
| **Additional** | .NET Framework 4.8 (included with Windows 10/11) | — |

---

## Installation Methods

Stratum provides two installation options:

1. **MSI Installer** (recommended) — Full installation with Start Menu and Desktop shortcuts,
   Add/Remove Programs support, and registry entries.
2. **Portable EXE** — Standalone executable that runs from any folder. No installation required.
   Ideal for USB drives or temporary use.

---

## Method 1: MSI Installer Installation

### Step 1: Download or Build the Installer

- **Pre-built:** Download `Stratum.msi` from the Woven Model distribution portal.
- **Build yourself:** From the `production/stratum/` directory, run:
  ```
  python build_msi.py
  ```
  This produces `stratum/dist/Stratum.msi`.

### Step 2: Run the Installer

1. Locate `Stratum.msi` in File Explorer and double-click it.
2. Windows SmartScreen may show a warning. Click **More info** → **Run anyway**.
3. The installation wizard will appear:

   ![Welcome Screen](images/msi_welcome.png)
   *The welcome screen displays product name and version.*

4. Click **Next**. The license agreement screen appears:

   ![License Agreement](images/msi_license.png)
   *Review the End User License Agreement. Accept to continue.*

5. Click **Next** to confirm the installation destination:

   ![Installation Folder](images/msi_folder.png)
   *Default location: C:\Program Files\Woven Model\Stratum\*

6. Click **Install** to begin the installation.

### Step 3: Installation Progress

The installer copies files and creates shortcuts. Progress is displayed:

![Installation Progress](images/msi_progress.png)

### Step 4: Completion

![Installation Complete](images/msi_complete.png)

Click **Finish** to exit the installer.

---

## Method 2: Portable EXE

### Step 1: Build or Download

- **Build yourself:** From the `production/stratum/` directory, run:
  ```
  python build_msi.py --portable
  ```
  This produces `stratum/dist/Stratum.exe`.

- **Pre-built:** Download `Stratum.exe` from the distribution portal.

### Step 2: Run

Simply double-click `Stratum.exe` to launch. No installation required.

> **Tip:** Move `Stratum.exe` to any folder on your computer or USB drive.
> On first run, the executable will create the following subdirectories next to itself:
> - `profiles/` — Saved trading strategy profiles
> - `reports/` — Generated analysis reports
> - `data/` — Market data cache
> - `logs/` — Application logs
> - `cache/` — Temporary cache files

---

## First-Time Setup

### 1. Launching Stratum

- **MSI Install:** Start Menu → Woven Model → Stratum
- **Desktop shortcut:** Double-click the Stratum icon on your desktop
- **Portable:** Double-click `Stratum.exe`

Splash screen appears briefly:

![Splash Screen](images/splash.png)

### 2. License Activation

On first launch, the License Manager dialog appears:

![License Manager](images/license_manager.png)

You have two options:

#### Option A: Trial Mode
- Click **Start Trial** to begin a free 30-day trial.
- Trial restrictions:
  - Maximum 10 backtesting runs per day
  - Limited to 3 strategy profiles
  - AI analysis reports watermarked
  - No export to PDF

#### Option B: Activate with License Key
1. Purchase a license from [wovenmodel.com](https://wovenmodel.com).
2. You will receive a license key in the format: `XXXXX-XXXXX-XXXXX-XXXXX`
3. In the License Manager dialog:
   - Enter your license key in the input field
   - Click **Activate**
4. On success, the application unlocks all features permanently.

#### Option C: Load License File
1. If you have a `license.lic` file (provided at purchase):
   - Click **Load License File**
   - Browse to and select your `license.lic` file
2. The application validates and activates automatically.

> **Offline Activation:** If your computer has no internet access:
> 1. Click **Offline Activation** in the License Manager
> 2. Follow the instructions to generate an activation request code
> 3. Email the code to jude@wovenmodel.com
> 4. You will receive an activation response file — load it via **Load License File**

### 3. Main Application Window

After successful license setup, the main window appears:

![Main Application](images/main_window.png)

Key areas:
- **Navigation sidebar** — Switch between Backtesting, AI Analysis, Reports, and Settings
- **Strategy panel** — Build and configure trading strategies
- **Chart area** — Visualise backtest results
- **Status bar** — Shows connection status and license information

---

## Uninstalling Stratum

### Via Settings (Windows 10/11)

1. Open **Settings** → **Apps** → **Installed apps**
2. Search for "Stratum"
3. Click the three dots (⋯) next to "Stratum — AI Trading Strategy Analyzer"
4. Click **Uninstall**
5. Confirm the uninstall prompt

### Via Control Panel (Classic)

1. Open **Control Panel** → **Programs and Features**
2. Find "Stratum — AI Trading Strategy Analyzer" in the list
3. Right-click and select **Uninstall**
4. Follow the wizard

### Via Start Menu

1. Open **Start Menu** → **Woven Model** folder
2. Click **Uninstall Stratum**
3. Confirm the uninstall prompt

> **Note:** Uninstalling via MSI removes all program files, shortcuts, and registry entries.
> Your personal data files (profiles, reports, cache) in `%APPDATA%\Woven Model\Stratum\` are
> preserved for future reinstallation. To fully remove all data, delete that folder manually.

---

## Troubleshooting

### Installation Issues

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| **"This app can't run on your PC"** | 32-bit Windows not supported | Ensure you are using 64-bit Windows 10 or 11 |
| **"Windows protected your PC"** | SmartScreen filter | Click **More info** → **Run anyway** |
| **"Another version is already installed"** | Attempting to downgrade | Uninstall the current version first, or use `--all` or same-version reinstall |
| **Installation hangs at 99%** | Antivirus scanning the executable | Temporarily disable real-time protection, or add an exception for `C:\Program Files\Woven Model\Stratum\` |
| **"Error 1920" service failed to start** | Permission issue | Run the installer **as Administrator** (right-click → Run as administrator) |
| **Installation fails with error 2503/2502** | Corrupted installer | Re-download or rebuild the MSI. Run installer as Administrator |

### Launch Issues

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| **Application does not start** | Missing dependencies or corrupt installation | Reinstall Stratum using the MSI |
| **"MSVCP140.dll not found"** | Missing Visual C++ Redistributable | Download and install from: [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| **"API-MS-WIN-CORE-* missing"** | Too old Windows version | Upgrade to Windows 10 64-bit or later |
| **White screen / crash on launch** | Damaged configuration | Delete `%APPDATA%\Woven Model\Stratum\` and restart |
| **"License validation failed"** | Clock skew or invalid license | Check system date/time. Contact jude@wovenmodel.com for a new license key |
| **Charts not rendering** | Missing GPU drivers | Update your graphics card drivers |

### Runtime Issues

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| **AI analysis fails** | No internet connection for model download | Check your internet connection. The AI model downloads on first use |
| **Backtesting slow** | Insufficient RAM | Close other applications. Upgrade to 8 GB RAM or more |
| **Cannot download market data** | Firewall or proxy blocking | Add an exception for `Stratum.exe` in your firewall |
| **"Out of memory" error** | Too many concurrent backtests | Reduce the number of parallel backtests in Settings |
| **Report export fails** | Disk full or permission denied | Free up disk space. Ensure you have write permissions to the reports directory |

### License and Activation

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| **"Invalid license key"** | Typo or wrong format | Re-enter carefully. Keys follow XXXXX-XXXXX-XXXXX-XXXXX format |
| **"License expired"** | Trial period ended | Purchase a full license at wovenmodel.com |
| **"Activation server unreachable"** | No internet or server down | Check your internet. Use offline activation procedure |
| **"License file corrupt"** | Damaged .lic file | Contact jude@wovenmodel.com for a replacement |

---

## Support

If you encounter issues not covered in this guide:

| Resource | Contact |
|----------|---------|
| **Email Support** | jude@wovenmodel.com |
| **Website** | https://wovenmodel.com |
| **Documentation** | See `production/docs/` for deployment and operational guides |

When contacting support, please include:
- Stratum version (check in Help → About)
- Your operating system version (Windows 10/11, build number)
- The full error message text or screenshot
- Steps to reproduce the issue

---

## Additional Resources

- **[Deployment Guide](../docs/DEPLOYMENT.md)** — Server setup and configuration
- **[API Reference](../docs/API.md)** — Licensing server API documentation
- **[Operations Guide](../docs/OPERATIONS.md)** — Server administration and maintenance
- **[Troubleshooting Guide](../docs/TROUBLESHOOTING.md)** — Comprehensive error reference

---

*Stratum — AI Trading Strategy Analyzer*
*Version 1.3.0 | © 2025 Woven Model. All rights reserved.*