/**
 * Was der geplante Live-Lauf am Issue tut: oeffnen, kommentieren, schliessen —
 * oder nichts.
 *
 * WARUM DAS EINE DATEI IST UND KEIN `script:`-BLOCK
 * ------------------------------------------------
 * Dasselbe Argument, das `classify_live_run.py` aus dem YAML geholt hat: Der
 * einzige Teil des Workflows, der etwas entscheidet, gehoert nicht an die
 * einzige Stelle, an der ihn niemand testen kann. In einem `script:`-String war
 * dieser Entscheidungsbaum genau das — vier Verzweigungen, jede mit Folgen fuer
 * einen Thread, den Menschen lesen, und keine davon ausfuehrbar ohne GitHub.
 *
 * Als Modul laesst er sich aufrufen: `live_issue.test.mjs` fuehrt alle vier
 * Pfade gegen eine erfundene API und prueft, was aufgerufen wurde.
 *
 * `.cjs`, weil `actions/github-script` das Modul per `require` laedt.
 *
 * Aufruf im Workflow:
 *     const handler = require(`${process.env.GITHUB_WORKSPACE}/scripts/live_issue.cjs`);
 *     await handler({ github, context, core, env: process.env });
 */

'use strict';

// Stabiles Praefix: Damit ein zweiter roter Lauf den bestehenden Thread
// verlaengert statt einen zweiten aufzumachen. Zehn Issues zur selben Sache
// liest niemand. Gilt auch fuer den Dauerausfall — der haengt seinen Titel
// hinten an, damit `startsWith` ihn weiter findet.
const PREFIX = 'Live-Tests gegen data.finance.admin.ch rot';
const LABEL = 'upstream';

/** Der Block mit der pytest-Ausgabe, den beide Issue-Texte anhaengen. */
function ausgabeBlock(tail) {
  return [
    '<details><summary>Letzte Zeilen der pytest-Ausgabe</summary>',
    '',
    '```',
    tail,
    '```',
    '',
    '</details>',
  ];
}

/**
 * Das Label anlegen, falls das Repo es noch nicht kennt: Sonst scheitert
 * `issues.create` beim allerersten roten Lauf — genau dann, wenn das Issue
 * gebraucht wird. Ein 422 heisst «existiert bereits» und ist kein Fehler.
 */
async function labelSicherstellen(github, context) {
  try {
    await github.rest.issues.createLabel({
      ...context.repo,
      name: LABEL,
      color: 'd93f0b',
      description: 'Vertrag mit einer externen Quelle betroffen',
    });
  } catch (e) {
    if (e.status !== 422) throw e;
  }
}

module.exports = async function ({ github, context, core, env, heute }) {
  const state = env.LIVE_STATE;
  const reason = env.LIVE_REASON || '';
  const tail = env.LIVE_TAIL || '(keine Ausgabe)';
  const streak = env.LIVE_STREAK || '?';
  const dauerausfall = env.LIVE_DAUERAUSFALL === 'true';

  const run =
    `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}` +
    `/actions/runs/${context.runId}`;
  // Das Datum kommt herein, damit der Test es festnageln kann. Ohne das
  // pruefte er gegen «heute» und waere an jedem anderen Tag ein anderer Test.
  const tag = heute || new Date().toISOString().slice(0, 10);

  // `issues.listForRepo` statt der Such-API: Die Suche hat ein eigenes,
  // knappes Rate-Limit und indexiert verzoegert — ein frisch geoeffnetes Issue
  // findet sie unter Umstaenden nicht, und dann legt der naechste rote Lauf ein
  // zweites an.
  const issues = await github.rest.issues.listForRepo({
    ...context.repo,
    state: 'open',
    labels: LABEL,
    per_page: 100,
  });
  const offen = issues.data.find((i) => !i.pull_request && i.title.startsWith(PREFIX));

  if (state === 'unknown' && !dauerausfall) {
    // Weder oeffnen noch schliessen. Der Lauf hat nichts ueber den Vertrag mit
    // data.finance.admin.ch festgestellt, und ein Issue, das auf so einen Lauf
    // hin zugeht, behauptet einen Vergleich, den es nicht gab. Sichtbar wird es
    // ueber den roten Job.
    //
    // Hier landet seit dem 17.8.2026 auch der Ausfall der Quelle: Sind ALLE
    // Fehlschlaege Transportfehler, war die Quelle nicht erreichbar — kein
    // Befund, kein Thread. Bis er anhaelt: ab dem dritten Lauf ohne Gruen
    // faellt `dauerausfall`, und dann geht doch eines auf.
    core.warning(`Live-Suite nicht ausgewertet: ${reason}. Am Issue wurde nichts geaendert.`);
    return 'nichts';
  }

  if (state === 'unknown') {
    // Dauerausfall. Kein Vertragsbruch — aber ein Server, der seine Daten seit
    // Tagen nicht laden kann, ist kaputt, auch wenn nicht er der Schuldige ist.
    const body = [
      `Die Live-Suite ist seit **${streak} Laeufen** nicht mehr gruen, und jeder`,
      'dieser Laeufe scheiterte am Transport: `data.finance.admin.ch` war nicht',
      'erreichbar.',
      '',
      `Lauf: ${run}`,
      `Einordnung: ${reason}`,
      '',
      '**Das ist kein gebrochener Vertrag.** Kein Feld hat sich bewegt, keine',
      'Kopfzeile wurde umbenannt — die Quelle antwortet gar nicht. Ein einzelner',
      'solcher Lauf oeffnet hier nichts; drei hintereinander schon, weil ein',
      'Server, der seine Daten nicht mehr laden kann, kaputt ist, egal wer schuld',
      'daran ist.',
      '',
      'Erste Schritte: den Dump von Hand abrufen und schauen, ob die Quelle',
      'antwortet — nicht aus der Fehlermeldung schliessen. Antwortet sie wieder,',
      'schliesst der naechste gruene Lauf dieses Issue von selbst.',
      '',
      ...ausgabeBlock(tail),
    ].join('\n');

    if (offen) {
      await github.rest.issues.createComment({
        ...context.repo,
        issue_number: offen.number,
        body: `Weiterhin nicht erreichbar am ${tag} (${streak} Laeufe).\n\n${body}`,
      });
      return 'kommentiert';
    }
    await labelSicherstellen(github, context);
    await github.rest.issues.create({
      ...context.repo,
      title: `${PREFIX} — Quelle seit ${streak} Laeufen nicht erreichbar (${tag})`,
      body,
      labels: [LABEL],
    });
    return 'geoeffnet';
  }

  if (state === 'finding') {
    const body = [
      'Die geplante Live-Suite gegen `data.finance.admin.ch` ist rot.',
      '',
      `Lauf: ${run}`,
      `Einordnung: ${reason}`,
      '',
      '**Mindestens ein Fehlschlag ist inhaltlich.** Ein reiner Ausfall der',
      'Quelle wäre `unknown` und hätte dieses Issue nicht geöffnet — hier hat',
      'also etwas über den Vertrag mit der Quelle gesprochen.',
      '',
      'Das sehen die Unit-Tests nicht: Ihre Fixtures sind aus derselben Annahme',
      'geschrieben wie der Code und können sie deshalb nicht widerlegen.',
      '',
      'Erst die Quelle abfragen, dann einordnen — nicht aus der Fehlermeldung',
      'schliessen.',
      '',
      ...ausgabeBlock(tail),
    ].join('\n');

    if (offen) {
      await github.rest.issues.createComment({
        ...context.repo,
        issue_number: offen.number,
        body: `Wieder rot am ${tag}.\n\n${body}`,
      });
      return 'kommentiert';
    }
    await labelSicherstellen(github, context);
    await github.rest.issues.create({
      ...context.repo,
      title: `${PREFIX} (${tag})`,
      body,
      labels: [LABEL],
    });
    return 'geoeffnet';
  }

  // clear — und nur hier wird zugemacht, weil nur hier wirklich verglichen und
  // nichts gefunden wurde.
  if (offen) {
    await github.rest.issues.createComment({
      ...context.repo,
      issue_number: offen.number,
      body: `Die Live-Suite ist wieder gruen (${reason}). Lauf: ${run}`,
    });
    await github.rest.issues.update({
      ...context.repo,
      issue_number: offen.number,
      state: 'closed',
      state_reason: 'completed',
    });
    return 'geschlossen';
  }
  return 'nichts';
};

module.exports.PREFIX = PREFIX;
module.exports.LABEL = LABEL;
