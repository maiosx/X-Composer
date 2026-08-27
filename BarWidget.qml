import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "x.composer"

  implicitWidth: glyph.implicitWidth
  implicitHeight: glyph.implicitHeight

  function toggleComposer() {
    if (!root.bar) return
    if (typeof root.bar.run === "function") {
      root.bar.run("omarchy-shell shell toggle x.composer")
      return
    }
    if (root.bar.shell && typeof root.bar.shell.toggle === "function")
      root.bar.shell.toggle("x.composer", "{}")
  }

  BarIconButton {
    id: glyph
    anchors.fill: parent
    bar: root.bar
    text: "X"
    tooltipText: "Compose on X"
    onPressed: function (mouseButton) {
      root.toggleComposer()
    }
  }
}
