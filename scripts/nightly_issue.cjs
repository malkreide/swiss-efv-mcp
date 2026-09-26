/**
 * Was der naechtliche Gate-Lauf am Issue tut: oeffnen, kommentieren,
 * schliessen — oder nichts.
 *
 * WARUM DAS EINE DATEI IST UND KEIN `script:`-BLOCK
 * ------------------------------------------------
 * Dasselbe Argument wie bei `live_issue.cjs`: Der einzige Teil des Workflows,
 * der etwas entscheidet, gehoert nicht an die einzige Stelle, an der ihn
 * niemand testen kann. `nightly_issue.test.mjs` faehrt jeden Pfad gegen eine
 * erfundene API und prueft, was aufgerufen wurde.
 *
 * `.cjs`, weil `actions/github-script` das Modul per `require` laedt.
 *
 * DREI ZUSTAENDE, NICHT ZWEI
 * --------------------------
 * `success` und `failure` sind die offensichtlichen. Der dritte ist der, an
 * dem `if: failure()` scheitert: Ein abgebrochener Lauf (`cancelled`) hat die
 * Gates nicht gefahren und sagt deshalb nichts ueber den Branch. Ein Issue,
 * das auf so einen Lauf hin aufgeht, behauptet einen Befund, den es nicht
 * gibt; eines, das zugeht, behauptet eine Entwarnung, die nicht gemessen
 * wurde. Also: nichts tun und es ins Log schreiben.
 *
 * Aufruf im Workflow:
 *     const handler = require(`${process.env.GITHUB_WORKSPACE}/scripts/nightly_issue.cjs`);
 *     await handler({ github, context, core, env: process.env });
 */

'use strict';

// Stabiles Praefix, damit ein zweiter roter Lauf den bestehenden Thread
// verlaengert statt einen zweiten aufzumachen. Zehn Issues zur selben Sache
// liest niemand.
const PREFIX = 'Naechtliche Gates auf main rot';
const LABEL = 'ci';

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
      color: '1d76db',
      description: 'Die Gates des Repos, nicht eine externe Quelle',
    });
  } catch (e) {
    if (e.status !== 422) throw e;
  }
}

module.exports = async function ({ github, context, core, env, heute }) {
  const ergebnis = env.GATES_RESULT;

  const run =
    `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}` +
    `/actions/runs/${context.runId}`;
  // Das Datum kommt herein, damit der Test es festnageln kann. Ohne das
  // pruefte er gegen «heute» und waere an jedem anderen Tag ein anderer Test.
  const tag = heute || new Date().toISOString().slice(0, 10);

  // `issues.listForRepo` statt der Such-API: Die Suche hat ein eigenes,
  // knappes Rate-Limit und indexiert verzoegert — ein frisch geoeffnetes Issue
  // findet sie unter Umstaenden nicht, und dann legt der naechste rote Lauf
  // ein zweites an.
  const issues = await github.rest.issues.listForRepo({
    ...context.repo,
    state: 'open',
    labels: LABEL,
    per_page: 100,
  });
  const offen = issues.data.find((i) => !i.pull_request && i.title.startsWith(PREFIX));

  if (ergebnis !== 'success' && ergebnis !== 'failure') {
    // Abgebrochen, uebersprungen, oder ein Zustand, den GitHub spaeter
    // hinzufuegt. Die Gates sind nicht gefahren, also ist nichts gemessen.
    core.warning(
      `Gates endeten mit "${ergebnis}" — weder gruen noch rot. Am Issue wurde nichts geaendert.`,
    );
    return 'nichts';
  }

  if (ergebnis === 'failure') {
    const body = [
      'Die fuenf Offline-Gates sind auf `main` rot — ohne dass jemand gepusht hat.',
      '',
      `Lauf: ${run}`,
      '',
      '**Das ist fast nie der Code.** Der Branch hat sich seit dem letzten',
      'gruenen Lauf nicht veraendert; was sich veraendert hat, ist die Aufloesung',
      'einer Abhaengigkeit mit offener Untergrenze. Genau diese Klasse hat',
      '`main` am 18.9.2026 drei Wochen lang latent rot gehalten, ohne dass ein',
      'Commit die Ursache trug.',
      '',
      'Erste Schritte: den Lauf oeffnen und schauen, **welches** Gate faellt und',
      'mit welcher Version — nicht aus dem Testnamen schliessen. `pip list` im',
      'Log nennt, was heute aufgeloest wurde.',
      '',
      'Faellt nur die Installation, kann es ein Aussetzer des Index sein; dann',
      'schliesst der naechste gruene Lauf dieses Issue von selbst.',
    ].join('\n');

    if (offen) {
      await github.rest.issues.createComment({
        ...context.repo,
        issue_number: offen.number,
        body: `Weiterhin rot am ${tag}.\n\n${body}`,
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

  // success — und nur hier wird zugemacht, weil nur hier wirklich gefahren
  // und nichts gefunden wurde.
  if (offen) {
    await github.rest.issues.createComment({
      ...context.repo,
      issue_number: offen.number,
      body: `Die naechtlichen Gates sind wieder gruen. Lauf: ${run}`,
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
