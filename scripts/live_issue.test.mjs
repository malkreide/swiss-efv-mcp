/**
 * Tests fuer live_issue.cjs — was der Live-Lauf am Issue tut.
 *
 * Vier Verzweigungen, jede mit Folgen fuer einen Thread, den Menschen lesen.
 * Solange sie in einem `script:`-String steckten, war keine davon ausfuehrbar:
 * Der Entscheidungsbaum wurde von Hand gelesen und geglaubt.
 *
 * Die GitHub-API ist hier erfunden und protokolliert nur, was aufgerufen wurde.
 * Das reicht, denn genau darum geht es — nicht ob ein HTTP-Request gelingt,
 * sondern ob ueberhaupt einer haette abgehen duerfen.
 *
 * `node:test` aus der Standardbibliothek, keine Abhaengigkeit. Laeuft ueber
 * `tests/test_live_issue.py` im bestehenden pytest-Gate mit, oder direkt:
 *     node --test scripts/live_issue.test.mjs
 *
 * Die Datei wird einzeln benannt, nicht als Verzeichnis: `node --test scripts/`
 * versucht den Ordner als Modul zu laden und endet in `MODULE_NOT_FOUND`
 * (Node 22.22 nachgemessen).
 */

import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const handler = require('./live_issue.cjs');

const HEUTE = '2026-08-17';

/** Eine erfundene Issues-API, die mitschreibt statt zu senden. */
function mockGithub(offeneIssues = [], { labelExistiert = true } = {}) {
  const aufrufe = [];
  return {
    aufrufe,
    rest: {
      issues: {
        listForRepo: async () => ({ data: offeneIssues }),
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

function mockContext() {
  return {
    repo: { owner: 'malkreide', repo: 'swiss-efv-mcp' },
    runId: 42,
    serverUrl: 'https://github.com',
  };
}

/** Ein offener Thread, wie ihn ein frueherer roter Lauf hinterlassen haette. */
const OFFEN = [{ number: 35, title: `${handler.PREFIX} (2026-08-16)`, pull_request: null }];

async function lauf(env, offeneIssues = [], optionen = {}) {
  const github = mockGithub(offeneIssues, optionen);
  const warnungen = [];
  const ergebnis = await handler({
    github,
    context: mockContext(),
    core: { warning: (m) => warnungen.push(m) },
    env,
    heute: HEUTE,
  });
  return { ergebnis, aufrufe: github.aufrufe, warnungen };
}

const TRANSPORT = {
  LIVE_STATE: 'unknown',
  LIVE_REASON: 'alle 4 Fehlschlag/Fehlschlaege sind Transportfehler',
  LIVE_TAIL: 'UpstreamError: …',
  LIVE_STREAK: '2',
  LIVE_DAUERAUSFALL: 'false',
};
const DAUERAUSFALL = { ...TRANSPORT, LIVE_STREAK: '3', LIVE_DAUERAUSFALL: 'true' };
const BEFUND = {
  LIVE_STATE: 'finding',
  LIVE_REASON: '1 Fehlschlag und 0 Fehler von 6 Test(s)',
  LIVE_TAIL: 'AssertionError: Spalte Saldo fehlt',
  LIVE_STREAK: '1',
  LIVE_DAUERAUSFALL: 'false',
};
const GRUEN = {
  LIVE_STATE: 'clear',
  LIVE_REASON: '6 von 6 Test(s) ausgefuehrt, alle gruen',
  LIVE_TAIL: '6 passed',
  LIVE_STREAK: '0',
  LIVE_DAUERAUSFALL: 'false',
};

test('kurzer Ausfall ruehrt das Issue nicht an', async () => {
  const { ergebnis, aufrufe, warnungen } = await lauf(TRANSPORT);
  assert.equal(ergebnis, 'nichts');
  assert.deepEqual(
    aufrufe,
    [],
    'ein Aussetzer von zwei Minuten darf keinen Thread aufmachen',
  );
  assert.match(warnungen[0], /nicht ausgewertet/);
});

test('kurzer Ausfall schliesst auch kein offenes Issue', async () => {
  // Der teuerste Fehler in der Gegenrichtung: Ein Lauf, der nichts geprueft
  // hat, darf keinen Befund zumachen — das behauptet einen Vergleich, den es
  // nicht gab.
  const { aufrufe } = await lauf(TRANSPORT, OFFEN);
  assert.deepEqual(aufrufe, []);
});

test('Dauerausfall oeffnet einen Thread und nennt die Zahl', async () => {
  const { ergebnis, aufrufe } = await lauf(DAUERAUSFALL);
  assert.equal(ergebnis, 'geoeffnet');
  const create = aufrufe.find((a) => a.was === 'create');
  assert.ok(create, 'ab dem dritten Lauf ohne Gruen gehoert ein Issue auf');
  assert.match(create.titel, /Quelle seit 3 Laeufen nicht erreichbar/);
  assert.deepEqual(create.labels, [handler.LABEL]);
  assert.match(create.body, /kein gebrochener Vertrag/);
});

test('Dauerausfall-Titel bleibt unter dem Praefix findbar', async () => {
  // Sonst faende der naechste Lauf den eigenen Thread nicht und legte einen
  // zweiten an — und der gruene Lauf schloesse keinen von beiden.
  const { aufrufe } = await lauf(DAUERAUSFALL);
  const create = aufrufe.find((a) => a.was === 'create');
  assert.ok(create.titel.startsWith(handler.PREFIX));
});

test('Dauerausfall kommentiert, wenn der Thread schon offen ist', async () => {
  const { ergebnis, aufrufe } = await lauf({ ...DAUERAUSFALL, LIVE_STREAK: '5' }, OFFEN);
  assert.equal(ergebnis, 'kommentiert');
  assert.equal(aufrufe.filter((a) => a.was === 'create').length, 0);
  const comment = aufrufe.find((a) => a.was === 'comment');
  assert.equal(comment.nummer, 35);
  assert.match(comment.body, /Weiterhin nicht erreichbar am 2026-08-17 \(5 Laeufe\)/);
});

test('Befund oeffnet einen Thread', async () => {
  const { ergebnis, aufrufe } = await lauf(BEFUND);
  assert.equal(ergebnis, 'geoeffnet');
  const create = aufrufe.find((a) => a.was === 'create');
  assert.equal(create.titel, `${handler.PREFIX} (${HEUTE})`);
  assert.match(create.body, /Mindestens ein Fehlschlag ist inhaltlich/);
});

test('Befund kommentiert einen offenen Thread', async () => {
  const { aufrufe } = await lauf(BEFUND, OFFEN);
  assert.equal(aufrufe.filter((a) => a.was === 'create').length, 0);
  assert.match(aufrufe.find((a) => a.was === 'comment').body, /Wieder rot am 2026-08-17/);
});

test('gruener Lauf schliesst den offenen Thread', async () => {
  const { ergebnis, aufrufe } = await lauf(GRUEN, OFFEN);
  assert.equal(ergebnis, 'geschlossen');
  assert.match(aufrufe.find((a) => a.was === 'comment').body, /wieder gruen/);
  const update = aufrufe.find((a) => a.was === 'update');
  assert.deepEqual({ nummer: update.nummer, state: update.state }, { nummer: 35, state: 'closed' });
});

test('gruener Lauf schliesst auch den Dauerausfall-Thread', async () => {
  // Der Titel des Dauerausfalls hat einen Zusatz; wuerde `startsWith` ihn
  // verpassen, blieb ein Thread fuer immer offen, obwohl die Quelle antwortet.
  const dauerThread = [
    {
      number: 51,
      title: `${handler.PREFIX} — Quelle seit 4 Laeufen nicht erreichbar (2026-08-16)`,
      pull_request: null,
    },
  ];
  const { ergebnis, aufrufe } = await lauf(GRUEN, dauerThread);
  assert.equal(ergebnis, 'geschlossen');
  assert.equal(aufrufe.find((a) => a.was === 'update').nummer, 51);
});

test('gruener Lauf ohne offenen Thread tut nichts', async () => {
  const { ergebnis, aufrufe } = await lauf(GRUEN);
  assert.equal(ergebnis, 'nichts');
  assert.deepEqual(aufrufe, []);
});

test('ein Pull Request mit demselben Titel wird nicht fuer den Thread gehalten', async () => {
  const pr = [{ number: 60, title: `${handler.PREFIX} (2026-08-16)`, pull_request: {} }];
  const { ergebnis, aufrufe } = await lauf(GRUEN, pr);
  assert.equal(ergebnis, 'nichts');
  assert.deepEqual(aufrufe, [], 'ein PR ist kein Issue und darf nicht zugemacht werden');
});

test('fehlendes Label wird angelegt, ein 422 stoert nicht', async () => {
  const { aufrufe } = await lauf(BEFUND, [], { labelExistiert: false });
  assert.equal(aufrufe.find((a) => a.was === 'label').name, handler.LABEL);
  assert.ok(aufrufe.find((a) => a.was === 'create'), 'das Issue muss trotzdem entstehen');
});

test('ein anderer Fehler beim Label wird nicht verschluckt', async () => {
  const github = mockGithub([]);
  github.rest.issues.createLabel = async () => {
    const e = new Error('kaputt');
    e.status = 500;
    throw e;
  };
  await assert.rejects(
    () =>
      handler({
        github,
        context: mockContext(),
        core: { warning: () => {} },
        env: BEFUND,
        heute: HEUTE,
      }),
    /kaputt/,
  );
});
