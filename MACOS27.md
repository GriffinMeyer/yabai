# macOS 27 preparation

This fork stages the scripting-addition fixes for an existing yabai + skhd setup.
It does not install or start yabai when you clone or build it.

## Source and scope

- Upstream: https://github.com/asmvik/yabai
- Upstream base: `dd845723416f5fe92af49fad5ebab00369e07edd`.
- Community source: https://github.com/AhsanFazal/yabai
- Imported revision: `992eff03200255594b25f6ebca7ac688dbc88563`.
- Branch: `macos27-ready`.
- Scripting-addition version: `2.1.33` (the CLI still reports `yabai-v7.1.25`).

The imported history preserves the original authors. It adds macOS 27 version
gates, Dock patterns and search windows, arm64e.x1 patterns, the 27.2 current-Space
selector fallback, and capability validation for functions removed in 27.2.
It also updates event handling needed for tiling on macOS 27.

This branch uses the scripting addition and its existing SIP/boot-argument
requirements. It does not include the separate SIP-enabled gesture patch.

Reports and limitations:

- https://github.com/asmvik/yabai/issues/2802
- https://github.com/asmvik/yabai/issues/2832
- https://github.com/asmvik/yabai/issues/2802#issuecomment-6449829130

The source author reports focus/create/destroy working on macOS 27.2 `26B123`
on an M4 Max. The arm64e.x1 path was checked statically, not on a live machine.
Multi-display behavior and 27.1 were not tested by that author. Moving an entire
Space between displays is unavailable on 27.2; moving an individual window to a
Space is a separate feature and must be tested independently.

## Local project

Expected checkout: `~/personal/yabai`.

Remotes:

- `origin`: your GitHub fork.
- `upstream`: asmvik/yabai.
- `macos27`: AhsanFazal/yabai, used to import the pinned community revision.

To add this checkout to the desktop app, use Add project and select the folder
above. Do not use a worktree unless you specifically want another checkout.

## Build without activation

Run from the checkout as your normal user:

```sh
git switch macos27-ready
make clean
make install
make -C tests
python3 -m unittest discover -s tests -p test_install_local.py -v
./bin/yabai --version
shasum -a 256 ./bin/yabai
```

Despite its name, upstream's `make install` target only builds an optimized
binary at `bin/yabai`; it does not replace the installed executable. `make clean`
ensures the embedded scripting addition is regenerated from the patched source.
Build sequentially: do not run these make targets with `-j`.

The existing test suite covers display geometry. The Python tests exercise the
installer with mocked signing, sudo, and service commands, checking that signing,
verification, or sudo preflight failures preserve the existing installation.
Neither suite covers Dock injection or live Space switching. A successful
build/test run does not certify macOS 27 compatibility.
The prepared binary is not signed with a personal signing identity. Installation
signs a staged copy before changing the existing binary or stopping its service.

## Before upgrading

1. Record the exact target macOS version and build. Match it to the reports above.
2. Make a current system backup and retain a way to boot the previous macOS.
   A separate APFS test volume or external installation lets you try the exact
   build before upgrading the main installation:
   https://support.apple.com/en-us/118282
3. Preserve the installed binary, resolved dotfile contents, launch agent, and
   scripting-addition sudoers configuration. A local example is below. Keep
   backups out of Git; `local-backups/` is ignored.
4. Confirm a usable code-signing identity in Keychain Access. The default is
   `yabai-cert`; `security find-identity -v -p codesigning` lists usable identities.
   Set `YABAI_CERT` explicitly if using another identity. A changed identity may
   require granting Accessibility and Screen Recording again.
5. Record the current SIP configuration and boot arguments; check them again on
   the test OS using the official yabai installation guidance. This project does
   not change either setting.

Example backup, run from the checkout immediately before activation:

```sh
backup="$PWD/local-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
cp -p "$HOME/.local/bin/yabai" "$backup/yabai"
cp -L "$HOME/.yabairc" "$backup/yabairc"
cp -L "$HOME/.skhdrc" "$backup/skhdrc"
cp -p "$HOME/Library/LaunchAgents/com.asmvik.yabai.plist" "$backup/"
sw_vers > "$backup/macos.txt"
csrutil status > "$backup/sip.txt"
shasum -a 256 "$backup/yabai" > "$backup/yabai.sha256"
```

Separately save `/private/etc/sudoers.d/yabai`, if present, with administrator
access. Do not commit its contents. Write down the backup directory for rollback.

## Activate only when ready

The existing setup uses `~/.local/bin/yabai`, and its launch agent has that path
first in PATH. Keep that location to avoid running a different Homebrew binary.
Only after the backup and signing checks, run from this checkout:

```sh
make install-local PREFIX="$HOME/.local" YABAI_CERT="yabai-cert"
```

Run as your normal user, not `sudo make`. This command changes the installation:
it builds, signs a staged copy, asks for sudo, stops/removes the old service,
replaces the binary, updates the hash-pinned sudoers entry, loads the scripting
addition, and starts the service. No activation was performed during preparation.
It preserves the existing skhd/yabai dotfiles.

If loading fails, do not interpret a successful `space --focus` exit status as
proof of switching. Check the actual visible destination and logs. A failed
activation can leave the service stopped; diagnose it before proceeding.

Confirm which executable is selected and whether the service queries work:

```sh
command -v yabai
"$HOME/.local/bin/yabai" --version
"$HOME/.local/bin/yabai" -m query --spaces --space
tail -n 50 "/tmp/yabai_${USER}.err.log"
```

## Acceptance on the target macOS build

- Option+1 through Option+8: reach each actual destination, including long jumps.
- Shift+Option+1 through Shift+Option+8: move a disposable window to occupied and
  empty Spaces; confirm its destination and expected focus behavior.
- Window focus, tiling, resizing, and re-layout after closing a window.
- Normal monitor arrangement, display focus, disconnect/reconnect, sleep/wake.
- Reboot and Dock restart: ensure the configured `dock_did_restart` signal loads
  the scripting addition again. Save work before deliberately restarting Dock.
- Keep native Mission Control switching available as an immediate fallback.

Use `yabai -m query --spaces --space` after each switch and inspect the index.
Do not rely on an exit code: an unresolved scripting-addition target can silently
acknowledge a request without changing Space.

## Rollback

The old 7.1.18 binary is a recovery option on the previous macOS, not a fix for
macOS 27. If macOS 27 validation fails, boot the preserved previous installation.

On that installation, stop the candidate service, restore the backed-up binary
to `~/.local/bin/yabai`, and restore the saved launch agent and sudoers entry
using administrator access as needed. Restore dotfiles only if they changed.
Validate sudoers with `sudo visudo -cf /private/etc/sudoers.d/yabai`, then reload
the old scripting addition with `sudo "$HOME/.local/bin/yabai" --load-sa` and
start the service with `"$HOME/.local/bin/yabai" --start-service`.

The original sudoers hash must match the restored signed binary. Never use the
candidate's hash with the old binary. If the new payload remains loaded in Dock,
restart Dock before loading the old payload. Save work first. Do not run
`make uninstall-local` as a rollback shortcut; it removes the installed binary
and sudoers entry.

## Keeping this fork current

```sh
git fetch upstream
git log --oneline HEAD..upstream/master
```

Review new upstream support before merging. Preserve this prepared branch and
pin a newly tested revision for each future macOS update. Do not automatically
replace this branch with a moving community branch.
