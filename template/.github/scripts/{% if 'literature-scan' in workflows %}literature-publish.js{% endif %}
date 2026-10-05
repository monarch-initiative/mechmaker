// File the leads the literature-scan agent returned. No model runs here. The
// agent read abstracts, which anyone can write, so it only names papers from
// the packet and says what each would add; this step takes every paper fact
// from the packet itself, chooses the labels, and creates the issues.

const MARKER = 'mech-lit-scan:v1';
const AUGMENT = 'Augment only the existing record. If this needs a new record, ' +
  'open a separate curation + high_effort issue instead.';
const PREPRINT = 'This is a preprint and has not been peer reviewed. ' +
  'It must not be the only support for a claim.';

function clean(text, max = 6000) {
  // An agent's or an abstract's words must not summon people or other agents.
  return String(text ?? '').replace(/@/g, '@​').trim().slice(0, max);
}

function oneLine(text, max) {
  return clean(text, 1000).replace(/\s+/g, ' ').slice(0, max);
}

function quoted(text) {
  return clean(text).split('\n').map(l => `> ${l}`).join('\n');
}

function issueFor(lead, paper) {
  const name = oneLine(lead.name, 100) || '(unnamed)';
  const record = lead.record ? String(lead.record) : '';
  const labels = ['curation', record ? 'low_effort' : 'high_effort', 'literature'];
  if (paper.preprint) labels.push('preprint');
  const title = record
    ? `[lit-scan] ${name}: ${oneLine(paper.title, 140)}`
    : `[lit-scan:new] ${name}: recent literature signal`;
  const lines = [
    `**${clean(paper.id, 100)}**: ${oneLine(paper.title, 500)}`,
    '',
    `- venue: ${oneLine(paper.venue, 200) || 'unknown'}; date: ${oneLine(paper.date, 20) || 'unknown'}`,
    `- DOI: ${oneLine(paper.doi, 200) || 'none'}; link: ${oneLine(paper.link, 300)}`,
    '',
    '**Abstract** (from Europe PMC)',
    '',
    quoted(paper.abstract || '(no abstract)'),
    '',
    '## Assessment',
    '',
  ];
  if (record) lines.push(`Record: \`${clean(record, 300)}\``, '');
  lines.push(clean(lead.assessment, 4000) || '(no assessment)', '');
  if (record) lines.push(AUGMENT, '');
  if (paper.preprint) lines.push(`_${PREPRINT}_`, '');
  lines.push(`<!-- ${MARKER} ${clean(paper.id, 100)} -->`);
  return { title, labels, body: lines.join('\n') };
}

async function alreadyFiled(github, repo, id) {
  const q = `repo:${repo.owner}/${repo.repo} is:issue is:open "${id}" in:body`;
  const { data } = await github.rest.search.issuesAndPullRequests({ q, per_page: 1 });
  return data.total_count > 0;
}

async function publish(github, repo, result, packet, { max = 5, log = console.log, warn = console.warn } = {}) {
  const leads = Array.isArray(result?.leads) ? result.leads : [];
  const papers = new Map((packet?.papers ?? []).map(p => [String(p.id), p]));
  const limit = Math.min(Math.max(Number.isSafeInteger(max) ? max : 5, 0), 10);
  const filed = [];
  const seen = new Set();
  for (const lead of leads) {
    if (filed.length >= limit) { warn(`Stopping at ${limit} issue(s).`); break; }
    const id = String(lead?.paper ?? '');
    const paper = papers.get(id);
    if (!paper) { warn(`Skipping ${id || '(no id)'}: not in the packet.`); continue; }
    if (seen.has(id)) continue;
    seen.add(id);
    if (lead.record && !(paper.matches ?? []).some(m => m.record === lead.record)) {
      warn(`Skipping ${id}: the packet does not match it to ${lead.record}.`); continue;
    }
    if (await alreadyFiled(github, repo, id)) { log(`Skipping ${id}: an open issue has it.`); continue; }
    const issue = issueFor(lead, paper);
    const { data } = await github.rest.issues.create({ ...repo, ...issue });
    log(`Filed #${data.number} for ${id}.`);
    filed.push(data.number);
  }
  if (!filed.length) log('No issues filed.');
  return { filed };
}

module.exports = { publish, issueFor, clean };
