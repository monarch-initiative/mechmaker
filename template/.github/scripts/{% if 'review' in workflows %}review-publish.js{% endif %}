// Post the review the review agent returned. No model runs here, and no code
// from the PR: this checks the review against the PR as it is now and posts
// it, so the agent's output reaches nothing it was not meant to.

const MARKER = 'mech-review:v1';
const SEVERITIES = ['error', 'warning', 'note'];
const CHECKLIST = [
  ['qc', '`just qc` would pass'],
  ['quotes', 'every quote supports its claim'],
  ['terms', 'terms are correct and specific'],
  ['scope', 'records are in scope and not duplicates'],
  ['history', 'history records are present and filled in'],
];

function clean(text, max = 6000) {
  // One agent's words must not summon people or other agents.
  return String(text ?? '').replace(/@/g, '@​').trim().slice(0, max);
}

function shape(review) {
  if (!review || typeof review !== 'object') return null;
  const findings = (Array.isArray(review.findings) ? review.findings : [])
    .filter(f => f && SEVERITIES.includes(f.severity) && String(f.body ?? '').trim())
    .slice(0, 50);
  return {
    verdict: review.verdict === 'approve' ? 'approve' : 'request_changes',
    checklist: review.checklist && typeof review.checklist === 'object' ? review.checklist : {},
    summary: clean(review.summary) || '(no summary)',
    findings,
  };
}

function listed(f) {
  const where = f.path ? ` \`${clean(f.path, 300)}${Number.isSafeInteger(f.line) ? `:${f.line}` : ''}\`` : '';
  return `- **${f.severity}**${where}: ${clean(f.body, 3000)}`;
}

function body(r, inlineFindings, note) {
  const lines = CHECKLIST.map(([key, text]) => `- [${r.checklist[key] === true ? 'x' : ' '}] ${text}`);
  lines.push('', r.summary);
  const rest = r.findings.filter(f => !inlineFindings.includes(f));
  if (rest.length) lines.push('', '**Findings**', '', ...rest.map(listed));
  if (note) lines.push('', `_${note}_`);
  lines.push('', `<!-- ${MARKER} -->`);
  return lines.join('\n');
}

async function publish(github, repo, review, { pr, sha, log = console.log, warn = console.warn } = {}) {
  const r = shape(review);
  if (!r) { warn('No review to post: the agent returned nothing usable.'); return { posted: null }; }
  if (!Number.isSafeInteger(pr) || !/^[0-9a-f]{40}$/.test(String(sha))) {
    warn('No review posted: the PR number or the reviewed commit is missing.'); return { posted: null };
  }
  const { data: pull } = await github.rest.pulls.get({ ...repo, pull_number: pr });
  if (pull.state !== 'open') { warn(`PR #${pr} is ${pull.state}; no review posted.`); return { posted: null }; }
  if (pull.head.repo?.full_name !== `${repo.owner}/${repo.repo}`) {
    warn(`PR #${pr} comes from a fork; no review posted.`); return { posted: null };
  }
  if (pull.head.sha !== sha) {
    warn(`PR #${pr} moved on to ${pull.head.sha.slice(0, 7)} after the review of ${sha.slice(0, 7)}; ` +
         'no review posted. Comment /review to review the new commit.');
    return { posted: null };
  }

  // Blocking findings decide the event, whatever the verdict says; the
  // verdict can only make a review stricter.
  const blocking = r.findings.some(f => f.severity !== 'note');
  const event = blocking || r.verdict === 'request_changes' ? 'REQUEST_CHANGES' : 'APPROVE';

  const files = new Set((await github.paginate(github.rest.pulls.listFiles, {
    ...repo, pull_number: pr, per_page: 100,
  })).map(f => f.filename));
  const inline = r.findings.filter(f => files.has(f.path) && Number.isSafeInteger(f.line) && f.line > 0);
  const comments = inline.map(f => ({
    path: f.path, line: f.line, side: 'RIGHT', body: `**${f.severity}**: ${clean(f.body, 3000)}`,
  }));

  const attempts = [
    { event, comments, inlineFindings: inline, note: '' },
    { event, comments: [], inlineFindings: [], note: '' },
  ];
  let lastError = null;
  for (const a of comments.length ? attempts : attempts.slice(1)) {
    try {
      await github.rest.pulls.createReview({
        ...repo, pull_number: pr, commit_id: sha, event: a.event,
        body: body(r, a.inlineFindings, a.note), comments: a.comments,
      });
      log(`Posted ${a.event} on PR #${pr} with ${a.comments.length} inline comment(s).`);
      return { posted: a.event, inline: a.comments.length };
    } catch (err) {
      lastError = err;
      warn(`${a.event} with ${a.comments.length} inline comment(s) failed: ${err.message}`);
    }
  }
  // GitHub refused the event itself, e.g. Actions may not approve here. Post
  // the same review as a comment, so the work is not lost, and say why.
  const note = `Posted as a comment: GitHub refused ${event} (${clean(lastError?.message, 300)}).`;
  await github.rest.pulls.createReview({
    ...repo, pull_number: pr, commit_id: sha, event: 'COMMENT', body: body(r, [], note), comments: [],
  });
  warn(note);
  return { posted: 'COMMENT', inline: 0 };
}

module.exports = { publish, shape, MARKER };
