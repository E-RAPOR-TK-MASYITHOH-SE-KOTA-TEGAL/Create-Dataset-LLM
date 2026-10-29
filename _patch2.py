path = r'd:\SKRIPSI HUSAIN MULYANSYAH\PROSES PEMBUATAN DATASET\templates\dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Replace handleLoginSubmit function
old = re.search(r'async function handleLoginSubmit\(e\).*?(?=\n        function handleLogout)', content, re.DOTALL)
if old:
    print("Found at:", old.start(), old.end())
    new_fn = '''async function handleLoginSubmit(e) {
            e.preventDefault();
            const u = document.getElementById("login-username").value.trim();
            const p = document.getElementById("login-password").value;
            const btn = document.getElementById("btn-login-submit");
            loginErrorMsg.style.display = "none";
            btn.disabled = true;
            btn.innerText = "Memverifikasi...";

            try {
                const res = await fetch("/api/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username: u, password: p })
                });

                const data = await res.json();
                if (res.ok && data.access_token) {
                    localStorage.setItem("skripsi_auth_token", data.access_token);
                    loginOverlay.classList.add("hidden");
                } else {
                    loginErrorMsg.innerText = data.detail || "Username atau password salah!";
                    loginErrorMsg.style.display = "block";
                }
            } catch (err) {
                loginErrorMsg.innerText = "Server belum aktif. Jalankan: python api_ai.py";
                loginErrorMsg.style.display = "block";
            } finally {
                btn.disabled = false;
                btn.innerText = "Masuk ke Dashboard";
            }
        }

        '''
    content = content[:old.start()] + new_fn + content[old.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched OK")
else:
    print("NOT FOUND — showing context:")
    i = content.find("handleLoginSubmit")
    print(repr(content[i:i+1000]))

