# GloryDay

## Releasing a new version

Build with PyInstaller first:
```
pyinstaller main.spec
```

Zip the dist folder:
```powershell
Compress-Archive -Path "dist\main.exe", "dist\asset" -DestinationPath "GloryDay_v1.1.zip" -Force
```

Create GitHub release:
```
gh release create v1.1 "GloryDay_v1.1.zip" --repo zzthomaszzz/Glory_days_beta --title "GloryDay Beta v1.1" --notes "..."
```

Releases: https://github.com/zzthomaszzz/Glory_days_beta/releases
