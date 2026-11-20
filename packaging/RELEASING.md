# Windows and Linux releases

The `Build release` workflow uses Python 3.12, Windows Server 2022 x64 and
Ubuntu 24.04 x86_64. Both jobs run `pytest -q` with Qt's offscreen platform
before packaging. Windows uses `OpenStatement.spec`; Linux uses the existing
`packaging/linux/build_release.sh`. Python and runtime dependencies are bundled
by PyInstaller. macOS builds remain local, using the existing README process.

## First manual test

1. Commit these changes and push your branch to GitHub yourself. Merge the workflow
   into the default branch so GitHub displays its **Run workflow** button.
2. Open https://github.com/apowell656/csv2ofx-gui/actions and select **Build release**.
3. Click **Run workflow**, select the branch to test, then **Run workflow**.
4. Wait for both platform jobs to pass. The release job must be **Skipped**.
5. Open the run summary and download the Windows and Linux artifacts within seven
   days. Unzip them to obtain the versioned `.exe`, `.deb`, and `.AppImage`.
6. Try the executable on Windows and the packages on Ubuntu 24.04. After downloading
   the AppImage, run `chmod +x OpenStatement-*-x86_64.AppImage`. Use
   `APPIMAGE_EXTRACT_AND_RUN=1 ./OpenStatement-<version>-x86_64.AppImage` if FUSE
   is unavailable. Test CSV loading, preview and export with sanitized sample data.

Manual builds never create or modify GitHub Releases, even when run against a tag.
No secrets or paid services are needed. Only the release job gets `contents: write`.

## Next release

1. Change `[project].version` in `pyproject.toml` to the next release version, such
   as `0.9.2`. Commit, push, and preferably complete a manual test first.
2. From that exact commit, create and push the matching tag yourself:

   ```bash
   git tag v0.9.2
   git push origin v0.9.2
   ```

   Substitute the actual project version in both commands. Both build jobs reject
   any tag that isn't exactly `v` followed by the version in `pyproject.toml`.
3. Wait for both builds and the release job. The release job downloads both build
   artifacts and checks all three filenames and sizes before uploading. It attaches
   them to an existing release for the tag, or creates a **draft** when absent.
   It never changes an existing release's publication status. If the existing
   release is already published, uploaded assets are immediately public.
4. Build macOS locally as described in the README, package it as usual, and open
   **Releases → the draft → Edit**. Drag the macOS distribution into the assets.
5. Review all four downloads and release notes. Click **Publish release** only
   when ready. The workflow never publishes a draft.

Release filenames are `OpenStatement-<version>-Windows-x64.exe`,
`openstatement_<version>_amd64.deb`, and
`OpenStatement-<version>-x86_64.AppImage`. The Windows `.exe` is the one-file
application and needs no installer or separate Python installation.

## Reruns and troubleshooting

- Open the failed Actions run and read the first failing step. Use **Re-run failed
  jobs** after transient network failures. Successful jobs' artifacts must still
  exist; after seven days, use **Re-run all jobs** to regenerate them.
- Uploads deliberately do not overwrite release assets. If an earlier attempt
  partially uploaded files, review and delete only the three Windows/Linux assets
  from that release before rerunning the release job. Keep the macOS asset.
- A version mismatch requires fixing the version/tag relationship. Workflow reruns
  use the original commit, so source fixes need a new commit and manual validation;
  prefer a new version tag rather than silently moving a released tag.
- Windows/PyInstaller: inspect the dependency install and build logs. Confirm the
  `.ico` asset is tracked and `dist/OpenStatement.exe` was built. Do not disable
  tests to work around a packaging error. Unsigned executables may prompt Windows
  SmartScreen; signing is outside this workflow.
- Qt tests use `QT_QPA_PLATFORM=offscreen` and `PYTEST_QT_API=pyside6`. Missing Linux
  shared libraries appear in the test or PyInstaller logs; add required system
  libraries to the Linux install step. For interactive use, remove any inherited
  `QT_QPA_PLATFORM=offscreen` setting.
- Linux packaging requires `fakeroot`, `dpkg-deb`, `desktop-file-validate`, and
  network access for appimagetool. The script validates Debian metadata and extracts
  both packages to check launchers, executable files, icons and desktop entries.
  Extraction avoids requiring FUSE on CI. Download failures stop the build.
- A release upload permission failure: check repository/organization Actions
  policy allows the built-in token's job-level `contents: write` permission.
- The bundled GUI is not launched unattended in CI: the existing smoke test
  constructs the main window without entering the event loop. Package checks
  validate structure; actual packaged GUI startup still needs the manual checks
  above on each OS.

Ubuntu 24.04 builds are not a promise of compatibility with older distributions;
PyInstaller does not bundle glibc or every system GUI library. The existing Linux
script downloads the upstream continuous appimagetool and Python development
requirements have lower bounds, so builds are consistent in process but not
bit-for-bit reproducible. Local Linux version overrides remain supported.
