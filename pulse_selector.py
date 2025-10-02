import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

class PulseSelector(Gtk.DropDown):
    device = GObject.Property(type=str, default="")

    def __init__(self, search = "", source=True):
        super().__init__()
        self.name = self.__class__.__name__

        self.search = search
        self.device = ""

        self.sources = self.get_audio_sources()

        self.store = Gtk.StringList()
        i = 0; idx = 0
        for src, desc in self.sources:
            self.store.append(desc)
            if search and search in src:
                self.device = src; idx = i; search = ""
                print(f"{self.name}[{self.search}]: Found: [{desc}]: {src}")
            i += 1
        if not self.device:
            self.device = self.sources[0][0]

        self.set_model( self.store )

        self.set_selected(idx)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_item)
        factory.connect("bind", self.bind_item)
        self.set_factory(factory)

        self.connect("notify::selected", self.on_selection_changed)

    def setup_item(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        list_item.set_child(label)

    def bind_item(self, factory, list_item):
        label = list_item.get_child()
        item = list_item.get_item()
        label.set_text(item.get_string())

    def on_selection_changed( self, dropdown, pspec ):
        idx = dropdown.get_selected()
        self.device = self.sources[idx][0]
        print(self.name, f"{self.device=}")
        # print(self.device)

    def get_audio_sources(self):
        import pulsectl
        pulse = pulsectl.Pulse('audio-selector')
        sources = pulse.source_list()
        return [(s.name, s.description) for s in sources if ".monitor" not in s.name]

### ----------Test part-----------------------------

class MainWindow(Gtk.ApplicationWindow):
    source = GObject.Property(type=str, default="")

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("App Test")
        self.set_default_size(300, 100)

        self.pulse_sel = PulseSelector("")
        self.set_child(self.pulse_sel)

if __name__ == "__main__":
    app = Gtk.Application(application_id="org.example.Application")
    app.connect("activate", lambda app: MainWindow(app).present())
    app.run()

