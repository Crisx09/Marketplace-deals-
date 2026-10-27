import json
import os

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.network.urlrequest import UrlRequest
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

try:
    import certifi
    CA = certifi.where()
except Exception:
    CA = None

Window.softinput_mode = "below_target"


def open_url(url):
    try:  # Android: apre l'annuncio nell'app Facebook/browser
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Activity = autoclass("org.kivy.android.PythonActivity").mActivity
        Activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    except Exception:
        import webbrowser
        webbrowser.open(url)


def field(hint, text="", **kw):
    return TextInput(hint_text=hint, text=text, multiline=False,
                     size_hint_y=None, height=dp(44), **kw)


class DealsApp(App):
    def build(self):
        self.store = JsonStore(os.path.join(self.user_data_dir, "cfg.json"))
        cfg = self.store.get("cfg") if self.store.exists("cfg") else {}
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        self.f = {
            "url": field("URL server (https://...)", cfg.get("url", "")),
            "token": field("Token", cfg.get("token", ""), password=True),
            "query": field("Cosa cerchi? (es. iPhone 13)", cfg.get("query", "")),
            "city": field("Città (es. milano)", cfg.get("city", "milano")),
            "max": field("Prezzo max € (opzionale)", cfg.get("max", ""), input_filter="int"),
            "thr": field("Sconto minimo % (es. 25)", cfg.get("thr", "25"), input_filter="int"),
        }
        for w in self.f.values():
            root.add_widget(w)
        self.btn = Button(text="Cerca occasioni", size_hint_y=None,
                          height=dp(52), on_release=self.scan)
        self.status = Label(text="", size_hint_y=None, height=dp(40))
        self.grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.grid)
        for w in (self.btn, self.status, sv):
            root.add_widget(w)
        return root

    def scan(self, *_):
        v = {k: w.text.strip() for k, w in self.f.items()}
        if not v["url"] or not v["query"]:
            self.status.text = "Inserisci URL del server e cosa cercare"
            return
        self.store.put("cfg", **v)
        body = json.dumps({
            "query": v["query"], "city": v["city"] or "milano",
            "max_price": int(v["max"]) if v["max"] else None,
            "threshold": int(v["thr"] or 25)})
        self.btn.disabled = True
        self.grid.clear_widgets()
        self.status.text = "Scansione in corso (fino a 1-2 minuti)..."
        UrlRequest(v["url"].rstrip("/") + "/scan", req_body=body, method="POST",
                   req_headers={"Content-Type": "application/json", "X-Token": v["token"]},
                   on_success=self.ok, on_failure=self.err, on_error=self.err,
                   timeout=240, ca_file=CA)

    def ok(self, _req, res):
        self.btn.disabled = False
        if res.get("reference") is None:
            self.status.text = f"Pochi annunci ({res.get('n', 0)}): confronto non affidabile"
            return
        deals = res["deals"]
        self.status.text = (f"{len(deals)} occasioni su {res['n']} annunci "
                            f"(prezzo mediano €{res['reference']:.0f})")
        for d in deals:
            b = Button(
                text=f"{d['title']}\n€{d['price']:.0f}  (-{d['discount']}% vs €{d['median']:.0f})\n{d['location']}",
                size_hint_y=None, height=dp(92), halign="left", valign="middle",
                on_release=lambda _b, u=d["url"]: open_url(u))
            b.bind(width=lambda w, x: setattr(w, "text_size", (x - dp(16), None)))
            self.grid.add_widget(b)

    def err(self, _req, res):
        self.btn.disabled = False
        msg = res.get("detail") if isinstance(res, dict) else res
        self.status.text = f"Errore: {msg}"


if __name__ == "__main__":
    DealsApp().run()
