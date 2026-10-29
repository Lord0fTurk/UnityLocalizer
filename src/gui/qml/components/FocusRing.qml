// FocusRing.qml — keyboard focus indicator drawn above whichever control holds focus.
// The custom button backgrounds replace Material's own indicator, so this one overlay
// covers every control. Declare it once as a direct child of the ApplicationWindow.
// Text inputs are skipped because they already tint their own border.
// An item can opt in by exposing `readonly property bool focusRingVisible`.
import QtQuick
import QtQuick.Window

Rectangle {
    id: ring

    readonly property Item target: Window.window ? Window.window.activeFocusItem : null
    readonly property bool wanted: target !== null && target !== undefined
        && target.cursorPosition === undefined
        && (target.visualFocus === true || target.focusRingVisible === true)

    property rect box: Qt.rect(0, 0, 0, 0)

    function sync() {
        if (!wanted || !parent) return;
        var origin = target.mapToItem(parent, 0, 0);
        box = Qt.rect(origin.x, origin.y, target.width, target.height);
    }

    onWantedChanged: sync()
    onTargetChanged: sync()

    // Re-measure while shown so the ring follows a control inside a scrolling view.
    Timer {
        interval: 100
        repeat: true
        running: ring.wanted
        onTriggered: ring.sync()
    }

    visible: wanted && box.width > 0
    x: box.x - 3
    y: box.y - 3
    width: box.width + 6
    height: box.height + 6
    radius: Theme.radiusControl + 3
    color: "transparent"
    border.width: 2
    border.color: Theme.borderFocus
    z: 9998
}
