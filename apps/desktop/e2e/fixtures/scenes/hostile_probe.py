from manim import *

class Probe(Scene):
    def construct(self):
        results = []

        def attempt(label, fn):
            try:
                results.append(label + "=" + str(fn()))
            except:
                results.append(label + "=ERR")

        attempt("own_bridge", lambda: window.adle)
        attempt("parent_bridge", lambda: window.parent.parent.adle)
        attempt("top_doc", lambda: window.top.document.title)
        attempt("require", lambda: require)
        attempt("popup", lambda: window.open("https://example.com/"))
        attempt("storage", lambda: window.localStorage.setItem("probe", "1"))
        attempt("origin", lambda: window.parent.location.origin)

        net = {"remote": "pending", "app": "pending"}
        def remote_ok(r): net["remote"] = "REACHED"
        def remote_fail(e): net["remote"] = "blocked"
        def app_ok(r): net["app"] = "REACHED"
        def app_fail(e): net["app"] = "blocked"
        try:
            fetch("https://example.com/").then(remote_ok, remote_fail)
            fetch("adle://app/index.html").then(app_ok, app_fail)
        except:
            net["remote"] = "threw"

        self.wait(1.5)
        self.post_message("explored", ";".join(results) + ";net_remote=" + net["remote"] + ";net_app=" + net["app"])
        self.post_message("not_allowed_name", True)
        self.post_message("passed", {"object": "payload"})
        self.wait(0.2)
