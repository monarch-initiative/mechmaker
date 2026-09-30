// Decide whether a comment author is trusted, and whether an untrusted
// comment carries something risky enough to hide.
// Adapted from DisMech's github-trust-gate.js (monarch-initiative/dismech,
// BSD-3-Clause), trimmed to what the comment guard uses.

const TRUSTED_PERMISSIONS = new Set(["admin", "maintain", "write", "triage"]);
const BOT_LOGINS = new Set(["claude", "app/claude", "github-actions", "github-actions[bot]"]);

const RISKY_COMMENT_PATTERNS = [
  {
    reason: "github_user_attachment",
    pattern: /https?:\/\/github\.com\/user-attachments\/files\/\d+\/[^\s)\]>"']+/i,
  },
  {
    reason: "archive_attachment",
    pattern:
      /(?:^|[^\w])[\w./:%?=&-]+\.(?:zip|7z|rar|tar\.gz|tgz|tar|gz|bz2|xz)(?:[?#][^\s)\]>"']*)?(?:[\s)\]>"']|$)/i,
  },
  {
    reason: "executable_attachment",
    // Script names are common in ordinary discussion, so only binaries and
    // installers count here.
    pattern:
      /(?:^|[^\w])[\w./:%?=&-]+\.(?:exe|msi|dmg|pkg|apk|jar|ps1|bat|cmd|vbs|scr)(?:[?#][^\s)\]>"']*)?(?:[\s)\]>"']|$)/i,
  },
  {
    // An untrusted user must not be able to summon an agent.
    reason: "agent_trigger",
    pattern: /(?:^|\s)(?:@claude\b|\/review\b)/i,
  },
];

function normalizeLogin(login) {
  return String(login || "").trim().toLowerCase();
}

function isBotLogin(login) {
  const normalized = normalizeLogin(login);
  return normalized.endsWith("[bot]") || BOT_LOGINS.has(normalized);
}

async function isTrustedLogin({ github, owner, repo, login }) {
  if (!login || isBotLogin(login)) return true;
  try {
    const response = await github.rest.repos.getCollaboratorPermissionLevel({
      owner, repo, username: login,
    });
    return TRUSTED_PERMISSIONS.has(response.data.permission);
  } catch (error) {
    console.log(`Treating ${login} as untrusted: ${error.message}`);
    return false;
  }
}

function classifyCommentRisk(body) {
  const text = String(body || "");
  const reasons = RISKY_COMMENT_PATTERNS.filter(({ pattern }) => pattern.test(text)).map(({ reason }) => reason);
  return { shouldMinimize: reasons.length > 0, classifier: "SPAM", reasons };
}

async function minimizeComment({ github, subjectId, classifier = "SPAM" }) {
  const mutation = `
    mutation($subjectId: ID!, $classifier: ReportedContentClassifiers!) {
      minimizeComment(input: {subjectId: $subjectId, classifier: $classifier}) {
        minimizedComment { isMinimized minimizedReason }
      }
    }
  `;
  return github.graphql(mutation, { subjectId, classifier });
}

module.exports = { isBotLogin, isTrustedLogin, classifyCommentRisk, minimizeComment };
