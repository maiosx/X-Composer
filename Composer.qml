pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

// Fullscreen overlay — black field, no panel chrome, no outline.
// The composer sits in the center in the system serif.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false

  readonly property var xtweet: shell && typeof shell.serviceFor === "function"
    ? shell.serviceFor("x.composer") : null
  readonly property bool serviceReady: xtweet !== null
  readonly property bool posting: serviceReady && xtweet.posting
  readonly property bool paidApi: serviceReady && xtweet.paidApi
  readonly property string actionLabel: serviceReady
    ? xtweet.actionLabel : "Continue in X"
  readonly property string modeText: serviceReady
    ? xtweet.modeLabel : "Service unavailable"
  readonly property string statusText: serviceReady
    ? xtweet.statusText : "The X composer service did not start."
  readonly property bool statusError: !serviceReady || xtweet.statusError
  readonly property bool canSubmit: serviceReady && xtweet.ready
    && !xtweet.posting && composer.text.trim().length > 0
  readonly property int charCount: composer.text.length
  readonly property int charLimit: 280
  readonly property int remaining: charLimit - charCount
  readonly property bool overLimit: remaining < 0

  readonly property color bg: "#000000"
  readonly property color fg: "#f4f1ea"
  readonly property color muted: "#8a8580"
  readonly property color subtle: "#5c564c"
  readonly property color urgent: "#c45c4a"
  readonly property color accent: "#ffffff"
  readonly property color accentFg: "#000000"
  readonly property string serifFamily: "serif"

  function open(payloadJson) {
    root.opened = true
    if (serviceReady) xtweet.refreshMode()
    Qt.callLater(function () {
      if (composer)
        composer.forceActiveFocus()
    })
  }

  function close() { root.opened = false }

  function dismiss() {
    root.opened = false
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "x.composer")
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function submit() {
    if (!root.canSubmit) return
    if (serviceReady) xtweet.submit()
  }

  function compose(text) {
    var result = serviceReady ? xtweet.compose(text) : "service-unavailable"
    root.open("{}")
    return result
  }

  IpcHandler {
    target: "xcomposer"
    function toggle(): void { root.toggle() }
    function open(): void { root.open("{}") }
    function close(): void { root.dismiss() }
    function status(): string { return root.opened ? "open" : "closed" }
    function compose(text: string): string { return root.compose(text) }
  }

  Connections {
    target: root.serviceReady ? root.xtweet : null
    function onClosePanelsRequested() { root.dismiss() }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: root.bg
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "x-composer"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    Rectangle {
      anchors.fill: parent
      color: root.bg
    }

    Text {
      anchors.centerIn: parent
      text: "X"
      color: root.fg
      opacity: 0.045
      font.pixelSize: Math.min(parent.width * 0.72, 360)
      font.family: root.serifFamily
      textFormat: Text.PlainText
      z: 0
    }

    Item {
      id: stage
      z: 1
      width: Math.min(parent.width - 48, 640)
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: parent.top
      anchors.bottom: parent.bottom
      anchors.topMargin: 22
      anchors.bottomMargin: 28

      Item {
        id: header
        width: parent.width
        height: 28
        anchors.top: parent.top

        Text {
          text: "X COMPOSER"
          color: root.muted
          font.pixelSize: 11
          font.letterSpacing: 3
          font.weight: Font.Medium
          font.family: "sans-serif"
          textFormat: Text.PlainText
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
        }

        Text {
          text: root.modeText
          color: root.serviceReady ? root.subtle : root.urgent
          font.pixelSize: 14
          font.family: root.serifFamily
          elide: Text.ElideRight
          textFormat: Text.PlainText
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          width: parent.width * 0.5
          horizontalAlignment: Text.AlignRight
        }
      }

      TextArea {
        id: composer
        width: parent.width
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: -8
        height: Math.min(
          Math.max(implicitHeight, 140),
          Math.max(140, stage.height - header.height - footer.height - 64)
        )
        text: root.serviceReady ? root.xtweet.draft : ""
        enabled: root.serviceReady
        readOnly: !root.serviceReady || !root.xtweet.ready || root.posting
        wrapMode: TextEdit.Wrap
        placeholderText: "What's happening?"
        color: root.fg
        selectionColor: "#2a2723"
        selectedTextColor: root.fg
        placeholderTextColor: root.subtle
        font.family: root.serifFamily
        font.pixelSize: 32
        leftPadding: 0
        rightPadding: 0
        topPadding: 0
        bottomPadding: 0
        selectByMouse: true
        background: Item {}
        Accessible.name: "Post text"

        onTextChanged: {
          if (root.serviceReady && text !== root.xtweet.draft)
            root.xtweet.setDraft(text)
        }

        Keys.onEscapePressed: function (event) {
          event.accepted = true
          root.dismiss()
        }
      }

      Item {
        id: footer
        width: parent.width
        height: 52
        anchors.bottom: parent.bottom

        Column {
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          anchors.right: postButton.left
          anchors.rightMargin: 16
          spacing: 4

          Text {
            width: parent.width
            elide: Text.ElideRight
            text: {
              if (root.statusText !== "") return root.statusText
              if (root.overLimit) return Math.abs(root.remaining) + " over"
              return root.remaining + " / " + root.charLimit
            }
            color: (root.statusError || root.overLimit) ? root.urgent : root.muted
            font.family: root.serifFamily
            font.pixelSize: 13
            textFormat: Text.PlainText
          }

          Text {
            text: "Esc to close"
            color: root.subtle
            font.pixelSize: 11
            font.family: "sans-serif"
            textFormat: Text.PlainText
          }
        }

        Rectangle {
          id: postButton
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          implicitWidth: Math.max(44, postLabel.implicitWidth + 32)
          implicitHeight: Math.max(44, postLabel.implicitHeight + 16)
          radius: height / 2
          color: root.accent
          opacity: root.canSubmit ? 1 : 0.35

          Text {
            id: postLabel
            anchors.centerIn: parent
            text: root.posting
              ? (root.paidApi ? "Posting…" : "Opening…")
              : root.actionLabel
            color: root.accentFg
            font.family: "sans-serif"
            font.pixelSize: 14
            font.weight: Font.Medium
            textFormat: Text.PlainText
          }

          MouseArea {
            anchors.fill: parent
            enabled: root.canSubmit
            hoverEnabled: true
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: root.submit()
          }
        }
      }
    }
  }
}
