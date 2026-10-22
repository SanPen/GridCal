import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml } from '../../VeraGridWeb/static/js/html.js';

test('edited equipment names remain text in network tooltips', () => {
    assert.equal(escapeHtml('<img src=x onerror="alert(1)">&\''),
        '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;');
    assert.equal(escapeHtml(null), '');
    assert.equal(escapeHtml(132), '132');
});

import joint from '../../VeraGridWeb/static/vendor/joint/joint-core.mjs';
import { SchematicEditor } from '../../VeraGridWeb/static/js/sld_canvas.js';

test('schematic terminals are stable bus connections and routes follow moved buses', () => {
    const graph = new joint.dia.Graph();
    const first = new joint.dia.Element({id: 'first', type: 'dia.Element', position: {x: 0, y: 0}, size: {width: 160, height: 20},
        center: {x: 80, y: 10}, ports: {groups: {bus: {position: {name: 'absolute'}}}, items: []}});
    const second = new joint.dia.Element({id: 'second', type: 'dia.Element', position: {x: 300, y: 0}, size: {width: 160, height: 20},
        center: {x: 380, y: 10}, ports: {groups: {bus: {position: {name: 'absolute'}}}, items: []}});
    const counts = new Map([['first', 2], ['second', 1]]);
    const source = SchematicEditor.prototype.terminal(first, 'line', counts);
    const extra = SchematicEditor.prototype.terminal(first, 'generator', counts);
    const target = SchematicEditor.prototype.terminal(second, 'line', counts);
    assert.deepEqual(source, {id: 'first', port: 'line'});
    assert.notEqual(first.getPort(source.port).args.x, first.getPort(extra.port).args.x);
    const wire = new joint.shapes.standard.Link({source, target, lane: 1});
    graph.resetCells([first, second, wire]);
    SchematicEditor.prototype.routeWire.call({graph}, wire);
    assert.deepEqual(wire.vertices(), [{x: 80, y: -100}, {x: 380, y: -100}]);
    second.set('center', {x: 500, y: 200});
    SchematicEditor.prototype.routeWire.call({graph}, wire);
    assert.deepEqual(wire.vertices(), [{x: 80, y: -100}, {x: 500, y: -100}]);
});
