import re

path = r'd:\SKRIPSI HUSAIN MULYANSYAH\PROSES PEMBUATAN DATASET\templates\dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Replace wheel + keydown block ─────────────────────────────────────
old_block = content[content.find("overlay.addEventListener(\"wheel\""):
                    content.find("        });", content.find("overlay.addEventListener(\"keydown\"")) + 12]
# Fine-grained: find the section between "// =====================\n        // MULTI-TERMINAL" and before it
# Use regex approach instead

pattern = re.compile(
    r'overlay\.addEventListener\("wheel".*?}\);[ \t]*\r?\n[ \t]*\r?\n'
    r'[ \t]*overlay\.addEventListener\("keydown".*?}\);',
    re.DOTALL
)

new_block = r"""overlay.addEventListener("wheel", (e) => {
            if (!isScreenPoweredOn || currentScreenMode !== "anydesk") return;
            e.preventDefault();
            socket.emit("mouse_control", { action: "scroll", deltaY: e.deltaY, deltaX: e.deltaX });
        }, { passive: false });

        overlay.addEventListener("keydown", (e) => {
            if (!isScreenPoweredOn || currentScreenMode !== "anydesk") return;
            const preventKeys = ["Tab","Backspace","Delete","Home","End","PageUp","PageDown",
                                 "ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "];
            if (preventKeys.includes(e.key) || e.ctrlKey || e.altKey || e.metaKey) {
                e.preventDefault();
            }
            socket.emit("keyboard_control", {
                key: e.key,
                text: (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) ? e.key : null,
                modifiers: { ctrl: e.ctrlKey, alt: e.altKey, shift: e.shiftKey, meta: e.metaKey }
            });
        });

        // ── Touch / Pointer events (mobile & tablet AnyDesk) ─────────────
        let touchStartDist = 0;
        let isDragging = false;

        overlay.addEventListener("touchstart", (e) => {
            if (!isScreenPoweredOn || currentScreenMode !== "anydesk") return;
            e.preventDefault();
            if (e.touches.length === 2) {
                const dx = e.touches[1].clientX - e.touches[0].clientX;
                const dy = e.touches[1].clientY - e.touches[0].clientY;
                touchStartDist = Math.hypot(dx, dy);
            } else {
                const c = getNormalizedCoords(e);
                socket.emit("mouse_control", { action: "mousedown", button: "left", x: c.x, y: c.y });
                isDragging = true;
            }
        }, { passive: false });

        overlay.addEventListener("touchmove", (e) => {
            if (!isScreenPoweredOn || currentScreenMode !== "anydesk") return;
            e.preventDefault();
            if (e.touches.length === 2) {
                const dx = e.touches[1].clientX - e.touches[0].clientX;
                const dy = e.touches[1].clientY - e.touches[0].clientY;
                const dist = Math.hypot(dx, dy);
                const delta = (dist - touchStartDist) * 0.5;
                touchStartDist = dist;
                socket.emit("mouse_control", { action: "scroll_zoom", delta });
            } else {
                const c = getNormalizedCoords(e);
                socket.emit("mouse_control", { action: "move", x: c.x, y: c.y });
            }
        }, { passive: false });

        overlay.addEventListener("touchend", (e) => {
            if (!isScreenPoweredOn || currentScreenMode !== "anydesk") return;
            e.preventDefault();
            if (isDragging) {
                const t = e.changedTouches[0];
                const rect = overlay.getBoundingClientRect();
                const cx = Math.max(0, Math.min(1, (t.clientX - rect.left) / rect.width));
                const cy = Math.max(0, Math.min(1, (t.clientY - rect.top) / rect.height));
                socket.emit("mouse_control", { action: "mouseup", button: "left", x: cx, y: cy });
                isDragging = false;
            }
        }, { passive: false });"""

result, count = pattern.subn(new_block, content)
print(f"Replacements made: {count}")
if count == 0:
    # Fallback: show what the pattern would need to match
    m = re.search(r'overlay\.addEventListener\("wheel"', content)
    if m:
        print("Found 'wheel' at:", m.start())
        print(repr(content[m.start():m.start()+800]))
    else:
        print("'wheel' listener not found at all.")
else:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(result)
    print("File patched successfully.")

