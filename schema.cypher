// ============================================================================
// NexusHelper: FalkorDB schema + seed data
// ----------------------------------------------------------------------------
// Run statements one at a time (FalkorDB executes a single query per call).
// Graph name suggestion: "nexushelper"
//
// NODE LABELS
//   Employee, Team, Service, Incident, Question, Solution, Evidence,
//   Source, Document, Decision
//
// RELATIONSHIPS
//   (Employee)-[:MEMBER_OF]->(Team)
//   (Employee)-[:EXPERT_IN {level}]->(Service)
//   (Team)-[:OWNS]->(Service)
//   (Service)-[:DEPENDS_ON]->(Service)
//   (Incident)-[:AFFECTS]->(Service)
//   (Incident)-[:RESOLVED_BY]->(Solution)
//   (Incident)-[:RELATED_TO]->(Incident)
//   (Question)-[:ABOUT]->(Incident|Service)
//   (Solution)-[:SUPPORTED_BY]->(Evidence)
//   (Solution)-[:SUPERSEDES]->(Solution)
//   (Solution)-[:CONTRADICTS]->(Solution)
//   (Evidence)-[:EXTRACTED_FROM]->(Source)
//   (Document)-[:DESCRIBES]->(Service)
//   (Incident|Solution|Document|Evidence)-[:VISIBLE_TO]->(Team)
//
// SHARED NODE PROPERTIES (on Incident, Solution, Document, Evidence)
//   visibility   : 'public' | 'restricted'   (restricted => needs a VISIBLE_TO edge)
//   status       : 'unverified' | 'human_confirmed' | 'deprecated'
//   valid_from   : epoch seconds
//   valid_to     : epoch seconds, or null if still valid
//   confidence   : 0.0 - 1.0
//   embedding    : vecf32 (Incident, Question, Document only)
// ============================================================================


// ----------------------------------------------------------------------------
// 1. INDEXES
// ----------------------------------------------------------------------------
CREATE INDEX FOR (e:Employee) ON (e.id)
CREATE INDEX FOR (t:Team) ON (t.id)
CREATE INDEX FOR (s:Service) ON (s.id)
CREATE INDEX FOR (s:Service) ON (s.name)
CREATE INDEX FOR (i:Incident) ON (i.id)
CREATE INDEX FOR (i:Incident) ON (i.visibility)
CREATE INDEX FOR (sol:Solution) ON (sol.id)
CREATE INDEX FOR (sol:Solution) ON (sol.status)

// Vector indexes: dimension must match your embedding model
// (384 = all-MiniLM-L6-v2, 1536 = text-embedding-3-small, etc.)
CREATE VECTOR INDEX FOR (i:Incident) ON (i.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}
CREATE VECTOR INDEX FOR (q:Question) ON (q.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}
CREATE VECTOR INDEX FOR (d:Document) ON (d.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}

// Full-text index for keyword fallback
CALL db.idx.fulltext.createNodeIndex('Document', 'title', 'body')

// Uniqueness constraints are NOT Cypher in FalkorDB. Run these as commands:
//   GRAPH.CONSTRAINT CREATE nexushelper UNIQUE NODE Employee PROPERTIES 1 id
//   GRAPH.CONSTRAINT CREATE nexushelper UNIQUE NODE Team PROPERTIES 1 id
//   GRAPH.CONSTRAINT CREATE nexushelper UNIQUE NODE Service PROPERTIES 1 id
//   GRAPH.CONSTRAINT CREATE nexushelper UNIQUE NODE Incident PROPERTIES 1 id
//   GRAPH.CONSTRAINT CREATE nexushelper UNIQUE NODE Solution PROPERTIES 1 id
// (A unique constraint requires an exact-match index on the same property.)


// ----------------------------------------------------------------------------
// 2. SEED DATA (single statement; run once)
//    Embeddings are NOT seeded here. Generate them in Python and set with:
//      MATCH (i:Incident {id:$id}) SET i.embedding = vecf32($vec)
// ----------------------------------------------------------------------------
CREATE
  // Teams
  (platform:Team   {id:'team-platform', name:'Platform'}),
  (security:Team   {id:'team-security', name:'Security'}),
  (payments:Team   {id:'team-payments', name:'Payments'}),

  // Employees
  (alice:Employee  {id:'emp-alice', name:'Alice Rao',  role:'SRE'}),
  (bob:Employee    {id:'emp-bob',   name:'Bob Mehta',  role:'Backend Engineer'}),
  (carol:Employee  {id:'emp-carol', name:'Carol Iyer', role:'Security Engineer'}),

  (alice)-[:MEMBER_OF]->(platform),
  (bob)-[:MEMBER_OF]->(payments),
  (carol)-[:MEMBER_OF]->(security),

  // Services (aliases feed the router's entity linker)
  (svcA:Service    {id:'svc-a',    name:'Service A',    aliases:['service a','svc-a','payments-api'], version:'2.4.1'}),
  (auth:Service    {id:'svc-auth', name:'Auth Service', aliases:['auth service','auth-svc','authentication service','auth'], version:'5.1.0'}),
  (gw:Service      {id:'svc-gw',   name:'API Gateway',  aliases:['api gateway','gateway','gw'], version:'3.0.2'}),

  (payments)-[:OWNS]->(svcA),
  (security)-[:OWNS]->(auth),
  (platform)-[:OWNS]->(gw),
  (svcA)-[:DEPENDS_ON]->(auth),
  (gw)-[:DEPENDS_ON]->(auth),
  (gw)-[:DEPENDS_ON]->(svcA),

  (alice)-[:EXPERT_IN {level:'high'}]->(svcA),
  (bob)-[:EXPERT_IN {level:'high'}]->(svcA),
  (carol)-[:EXPERT_IN {level:'high'}]->(auth),

  // Sources
  (src1:Source {id:'src-slack-1', type:'slack', url:'https://example.slack.com/archives/C01/p1', ts:1738000000}),
  (src2:Source {id:'src-jira-1',  type:'jira',  url:'https://example.atlassian.net/browse/OPS-101', ts:1739000000}),
  (src3:Source {id:'src-doc-1',   type:'doc',   url:'https://example.com/docs/deploy-service-a', ts:1740000000}),
  (src4:Source {id:'src-jira-2',  type:'jira',  url:'https://example.atlassian.net/browse/SEC-77', ts:1741000000}),

  // Public runbook
  (doc1:Document {id:'doc-deploy-a', title:'Service A deployment procedure',
                  body:'1. Freeze merges. 2. Run migrations. 3. Canary at 5 percent. 4. Verify auth token refresh. 5. Roll out.',
                  visibility:'public', status:'human_confirmed', valid_from:1740000000, valid_to:null, confidence:0.95}),
  (doc1)-[:DESCRIBES]->(svcA),

  // Incidents: three repeated Service A failures after deploys, linked to auth
  (inc1:Incident {id:'inc-101', title:'Service A 502s after deploy v2.3.0',
                  summary:'Token validation timeouts against Auth Service after rollout.',
                  visibility:'public', status:'human_confirmed', valid_from:1738000000, valid_to:null, confidence:0.8}),
  (inc2:Incident {id:'inc-102', title:'Service A login loop after deploy v2.4.0',
                  summary:'Expired signing keys cached by Service A; auth rejected refreshes.',
                  visibility:'public', status:'human_confirmed', valid_from:1739000000, valid_to:null, confidence:0.85}),
  (inc3:Incident {id:'inc-103', title:'Service A 401 spike after deploy v2.4.1',
                  summary:'JWKS cache TTL longer than key rotation interval.',
                  visibility:'public', status:'unverified', valid_from:1741000000, valid_to:null, confidence:0.6}),

  // Restricted incident: only Security can see it (access-control demo)
  (inc4:Incident {id:'inc-104', title:'Auth key rotation exposed signing key in logs',
                  summary:'Signing key material appeared in debug logs during rotation. Rotated and purged.',
                  visibility:'restricted', status:'human_confirmed', valid_from:1741000000, valid_to:null, confidence:0.9}),
  (inc4)-[:VISIBLE_TO]->(security),

  (inc1)-[:AFFECTS]->(svcA), (inc1)-[:AFFECTS]->(auth),
  (inc2)-[:AFFECTS]->(svcA), (inc2)-[:AFFECTS]->(auth),
  (inc3)-[:AFFECTS]->(svcA), (inc3)-[:AFFECTS]->(auth),
  (inc4)-[:AFFECTS]->(auth),
  (inc2)-[:RELATED_TO]->(inc1),
  (inc3)-[:RELATED_TO]->(inc2),
  (inc3)-[:RELATED_TO]->(inc4),

  // Solutions, including a superseded one
  (sol1:Solution {id:'sol-1', title:'Restart Service A pods after deploy',
                  detail:'Restart clears cached keys. Temporary only.',
                  visibility:'public', status:'deprecated', valid_from:1738000000, valid_to:1739500000, confidence:0.4}),
  (sol2:Solution {id:'sol-2', title:'Refresh JWKS cache on deploy hook',
                  detail:'Add a post-deploy hook that forces a JWKS refresh before traffic shifts.',
                  visibility:'public', status:'human_confirmed', valid_from:1739500000, valid_to:null, confidence:0.88}),
  (sol3:Solution {id:'sol-3', title:'Align JWKS cache TTL with key rotation interval',
                  detail:'Set Service A cache TTL below the rotation interval. Pending confirmation.',
                  visibility:'public', status:'unverified', valid_from:1741000000, valid_to:null, confidence:0.6}),

  (inc1)-[:RESOLVED_BY]->(sol1),
  (inc2)-[:RESOLVED_BY]->(sol2),
  (inc3)-[:RESOLVED_BY]->(sol3),
  (sol2)-[:SUPERSEDES]->(sol1),
  (sol3)-[:SUPERSEDES]->(sol2),

  // Evidence with provenance
  (ev1:Evidence {id:'ev-1', summary:'Slack thread: pods restarted, 502s stopped for a day.',
                 visibility:'public', status:'human_confirmed', valid_from:1738000000, valid_to:null, confidence:0.5}),
  (ev2:Evidence {id:'ev-2', summary:'OPS-101: post-deploy JWKS refresh stopped login loops across two releases.',
                 visibility:'public', status:'human_confirmed', valid_from:1739500000, valid_to:null, confidence:0.9}),
  (ev3:Evidence {id:'ev-3', summary:'SEC-77: key rotation every 6h, Service A cache TTL is 24h.',
                 visibility:'public', status:'human_confirmed', valid_from:1741000000, valid_to:null, confidence:0.8}),

  (sol1)-[:SUPPORTED_BY]->(ev1), (sol2)-[:SUPPORTED_BY]->(ev2), (sol3)-[:SUPPORTED_BY]->(ev3),
  (ev1)-[:EXTRACTED_FROM]->(src1),
  (ev2)-[:EXTRACTED_FROM]->(src2),
  (ev3)-[:EXTRACTED_FROM]->(src4),

  (doc1)-[:EXTRACTED_FROM]->(src3),
  (sol2)-[:VISIBLE_TO]->(platform), (sol3)-[:VISIBLE_TO]->(payments)


// ============================================================================
// 3. PERMISSION-SCOPED QUERY TEMPLATES
//    The backend resolves $scope (list of team ids) from the authenticated
//    session. NEVER take it from the request body or from the LLM.
//    Filtering happens before retrieval, so restricted nodes never reach
//    the model context.
// ============================================================================

// ---- Q1: Tier 1 lookup, approved documentation for a service --------------
// params: {service: 'svc-a', scope: ['team-payments']}
MATCH (d:Document)-[:DESCRIBES]->(s:Service {id:$service})
OPTIONAL MATCH (d)-[:VISIBLE_TO]->(t:Team)
WITH d, collect(t.id) AS teams
WHERE d.visibility = 'public' OR any(x IN teams WHERE x IN $scope)
  AND d.status <> 'deprecated' AND d.valid_to IS NULL
RETURN d.id, d.title, d.body, d.confidence
ORDER BY d.confidence DESC
LIMIT 3

// ---- Q2: Hybrid retrieval, vector entry points then permission filter -----
// params: {embedding: [...], scope: [...], k: 20}
// Over-fetch (k=20), filter, then keep the best 5.
CALL db.idx.vector.queryNodes('Incident', 'embedding', $k, vecf32($embedding))
YIELD node AS i, score
OPTIONAL MATCH (i)-[:VISIBLE_TO]->(t:Team)
WITH i, score, collect(t.id) AS teams
WHERE i.visibility = 'public' OR any(x IN teams WHERE x IN $scope)
RETURN i.id, i.title, score
ORDER BY score
LIMIT 5

// ---- Q3: Tier 3 investigation subgraph (1-3 hops, scoped) -----------------
// params: {incident_ids: ['inc-101','inc-102','inc-103'], scope: [...]}
// Returns compact facts; the LLM never sees raw documents.
MATCH (i:Incident) WHERE i.id IN $incident_ids
OPTIONAL MATCH (i)-[:VISIBLE_TO]->(it:Team)
WITH i, collect(it.id) AS iteams
WHERE i.visibility = 'public' OR any(x IN iteams WHERE x IN $scope)
OPTIONAL MATCH (i)-[:AFFECTS]->(s:Service)
OPTIONAL MATCH (i)-[:RESOLVED_BY]->(sol:Solution)
OPTIONAL MATCH (sol)-[:SUPPORTED_BY]->(ev:Evidence)-[:EXTRACTED_FROM]->(src:Source)
OPTIONAL MATCH (sol)-[:SUPERSEDES]->(old:Solution)
RETURN i.id AS incident, i.title AS incident_title,
       collect(DISTINCT s.id) AS services,
       sol.id AS solution, sol.status AS sol_status, sol.valid_to AS sol_valid_to,
       collect(DISTINCT old.id) AS supersedes,
       collect(DISTINCT {evidence: ev.id, source: src.url, ts: src.ts}) AS evidence

// ---- Q4: Verification, freshness + supersession check ---------------------
// params: {solution_ids: [...]}
MATCH (sol:Solution) WHERE sol.id IN $solution_ids
OPTIONAL MATCH (newer:Solution)-[:SUPERSEDES]->(sol)
OPTIONAL MATCH (sol)-[:CONTRADICTS]-(c:Solution)
RETURN sol.id, sol.status, sol.valid_to IS NOT NULL AS expired,
       collect(DISTINCT newer.id) AS superseded_by,
       collect(DISTINCT c.id) AS contradicted_by

// ---- Q5: Expert routing when the graph has no answer ----------------------
// params: {service: 'svc-auth'}
MATCH (e:Employee)-[x:EXPERT_IN]->(s:Service {id:$service})
RETURN e.id, e.name, x.level
ORDER BY x.level

// ---- Q6: Learning loop write-back after user confirms "this worked" -------
// params: {incident_id, solution_id, evidence_id, ts}
MATCH (i:Incident {id:$incident_id})-[:RESOLVED_BY]->(sol:Solution {id:$solution_id})
SET sol.status = 'human_confirmed',
    sol.confidence = CASE WHEN sol.confidence + 0.1 > 1.0 THEN 1.0 ELSE sol.confidence + 0.1 END,
    sol.last_confirmed = $ts
RETURN sol.id, sol.status, sol.confidence

// ---- Q7: Evidence subgraph for the demo visual -----------------------------
// params: {incident_ids: [...]}. Returns nodes and edges for the UI to render.
MATCH p = (i:Incident)-[*1..2]-(n)
WHERE i.id IN $incident_ids AND NOT n:Employee
RETURN p
LIMIT 200

// ---- Access control demo: same question, different scope ------------------
// Alice (Platform): scope ['team-platform']  -> does NOT see inc-104
// Carol (Security): scope ['team-security']  -> sees inc-104
MATCH (i:Incident)-[:AFFECTS]->(:Service {id:'svc-auth'})
OPTIONAL MATCH (i)-[:VISIBLE_TO]->(t:Team)
WITH i, collect(t.id) AS teams
WHERE i.visibility = 'public' OR any(x IN teams WHERE x IN $scope)
RETURN i.id, i.title
