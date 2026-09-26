/**
 * Tests fuer nightly_issue.cjs — was der naechtliche Gate-Lauf am Issue tut.
 *
 * Die GitHub-API ist hier erfunden und protokolliert nur, was aufgerufen
 * wurde. Das reicht, denn genau darum geht es — nicht ob ein HTTP-Request
 * gelingt, sondern ob ueberhaupt einer haette abgehen duerfen.
 *
 * `node:test` aus der Standardbibliothek, keine Abhaengigkeit. Laeuft ueber
 * `tests/test_nightly_issue.py` im bestehenden pytest-Gate mit, oder direkt:
 *     node --test scripts/nightly_issue.test.mjs
 */

import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const handler = require('./nightly_issue.cjs');

const HEUTE = '2026-09-26';
const PREFIX = 'Naechtliche Gates auf main rot';

/** Eine erfundene Issues-API, die mitschreibt statt zu senden. */
function mockGithub(offeneIssues = [], { labelExistiert = true } = {}) {
  const aufrufe = [];
  return {
    aufrufe,
    rest: {
      issues: {
        listForRepo: async (a) => {
          aufrufe.push({ was: 'list', labels: a.labels, state: a.state });
          return { data: offeneIssues };
        },
        create: async (a) => {
          aufrufe.push({ was: 'create', titel: a.title, body: a.body, labels: a.labels });
        },
        createComment: async (a) => {
          aufrufe.push({ was: 'comment', nummer: a.issue_number, body: a.body });
        },
        update: async (a) => {
          aufrufe.push({ was: 'update', nummer: a.issue_number, state: a.state });
        },
        createLabel: async (a) => {
          aufrufe.push({ was: 'label', name: a.name });
          if (labelExistiert) {
            const e = new Error('already_exists');
            e.status = 422;
            throw e;
          }
        },
      },
    },
  };
}

const context = {
  repo: { owner: 'malkreide', repo: 'swiss-efv-mcp' },
  serverUrl: 'https://github.com',
  runId: 12345,
};

function mockCore() {
  const warnungen = [];
  return { warnungen, warning: (m) => warnungen.push(m), info: () => {} };
}

function lauf(github, core, ergebnis) {
  return handler({ github, context, core, env: { GATES_RESULT: ergebnis }, heute: HEUTE });
}

test('rot ohne offenes Issue oeffnet eines', async () => {
  const github = mockGithub([]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'failure'), 'geoeffnet');

  const create = github.aufrufe.find((a) => a.was === 'create');
  assert.ok(create, 'kein Issue angelegt');
  assert.equal(create.titel, `${PREFIX} (${HEUTE})`);
  assert.deepEqual(create.labels, ['ci']);
  assert.match(create.body, /actions\/runs\/12345/);
  // Der Text muss sagen, dass der Code wahrscheinlich nicht schuld ist —
  // sonst sucht der naechste Leser im Diff, in dem nichts steht.
  assert.match(create.body, /offener Untergrenze/);
});

test('rot mit offenem Issue kommentiert, statt ein zweites zu oeffnen', async () => {
  const github = mockGithub([{ number: 7, title: `${PREFIX} (2026-09-20)` }]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'failure'), 'kommentiert');

  assert.ok(!github.aufrufe.some((a) => a.was === 'create'), 'zweites Issue angelegt');
  const kommentar = github.aufrufe.find((a) => a.was === 'comment');
  assert.equal(kommentar.nummer, 7);
  assert.match(kommentar.body, new RegExp(`Weiterhin rot am ${HEUTE}`));
});

test('gruen mit offenem Issue schliesst es', async () => {
  const github = mockGithub([{ number: 7, title: `${PREFIX} (2026-09-20)` }]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'success'), 'geschlossen');

  const update = github.aufrufe.find((a) => a.was === 'update');
  assert.equal(update.nummer, 7);
  assert.equal(update.state, 'closed');
  assert.ok(
    github.aufrufe.some((a) => a.was === 'comment' && a.nummer === 7),
    'ohne Kommentar zugemacht — der Thread sagt dann nicht, warum',
  );
});

test('gruen ohne offenes Issue tut nichts', async () => {
  const github = mockGithub([]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'success'), 'nichts');
  assert.ok(
    !github.aufrufe.some((a) => ['create', 'comment', 'update'].includes(a.was)),
    'gruener Lauf hat am Issue etwas getan',
  );
});

test('abgebrochen oeffnet nichts und schliesst nichts', async () => {
  // Der Zustand, an dem `if: failure()` scheitert: Die Gates sind nicht
  // gefahren. Ein Issue waere ein erfundener Befund, ein Schliessen eine
  // erfundene Entwarnung.
  const github = mockGithub([{ number: 7, title: `${PREFIX} (2026-09-20)` }]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'cancelled'), 'nichts');

  assert.ok(
    !github.aufrufe.some((a) => ['create', 'comment', 'update'].includes(a.was)),
    'abgebrochener Lauf hat am Issue etwas getan',
  );
  assert.equal(core.warnungen.length, 1, 'kein Hinweis im Log');
  assert.match(core.warnungen[0], /cancelled/);
});

test('ein unbekannter Zustand faellt in denselben Zweig wie abgebrochen', async () => {
  // Gegenprobe zur Zeile darueber: Der Code prueft auf `success`/`failure` und
  // nicht auf `cancelled`. Kaeme bei GitHub ein sechster Zustand dazu, darf er
  // nicht als Befund durchgehen.
  const github = mockGithub([]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'was-es-2027-gibt'), 'nichts');
  assert.ok(!github.aufrufe.some((a) => a.was === 'create'));
});

test('das Label wird angelegt, bevor das erste Issue aufgeht', async () => {
  // Ohne das scheitert `issues.create` beim allerersten roten Lauf — genau
  // dann, wenn das Issue gebraucht wird.
  const github = mockGithub([], { labelExistiert: false });
  const core = mockCore();
  assert.equal(await lauf(github, core, 'failure'), 'geoeffnet');

  const reihenfolge = github.aufrufe.map((a) => a.was);
  // Erst die Anwesenheit, dann die Reihenfolge. Fehlte der Label-Aufruf ganz,
  // waere `indexOf('label')` gleich -1 und der Vergleich `-1 < 1` trotzdem
  // wahr — die Zusicherung haette genau dann gehalten, wenn sie greifen muss.
  // In der Gegenprobe am 26.9.2026 aufgefallen: `labelSicherstellen` entfernt,
  // Test blieb gruen.
  assert.ok(reihenfolge.includes('label'), `kein Label angelegt: ${reihenfolge.join(' -> ')}`);
  assert.ok(
    reihenfolge.indexOf('label') < reihenfolge.indexOf('create'),
    `Label nach dem Issue angelegt: ${reihenfolge.join(' -> ')}`,
  );
});

test('ein bestehendes Label (422) ist kein Fehler', async () => {
  const github = mockGithub([], { labelExistiert: true });
  const core = mockCore();
  assert.equal(await lauf(github, core, 'failure'), 'geoeffnet');
});

test('ein Pull Request mit demselben Titel gilt nicht als offenes Issue', async () => {
  // `listForRepo` liefert PRs mit. Ohne den Filter kommentierte der Lauf in
  // einen PR-Thread und liesse das eigentliche Issue ungeoeffnet.
  const github = mockGithub([
    { number: 9, title: `${PREFIX} (2026-09-20)`, pull_request: { url: 'x' } },
  ]);
  const core = mockCore();
  assert.equal(await lauf(github, core, 'failure'), 'geoeffnet');
  assert.ok(!github.aufrufe.some((a) => a.was === 'comment'), 'in einen PR kommentiert');
});
