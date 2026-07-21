<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ANU Mind - Documentation d'Architecture</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --text-color: #c9d1d9;
            --heading-color: #58a6ff;
            --border-color: #30363d;
            --code-bg: #161b22;
            --accent-green: #238636;
            --accent-purple: #8957e5;
            --accent-red: #f85149;
            --blockquote-border: #8b949e;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
        }

        h1, h2, h3, h4 {
            color: var(--text-color);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.3em;
            margin-top: 1.5em;
        }
        
        h1 { font-size: 2.2em; border-bottom: none; text-align: center; color: var(--heading-color); }
        h2 { font-size: 1.75em; color: var(--heading-color); }
        h3 { font-size: 1.25em; border-bottom: none; }

        a { color: var(--heading-color); text-decoration: none; }
        a:hover { text-decoration: underline; }

        blockquote {
            margin: 0;
            padding: 0.5em 1em;
            color: #8b949e;
            border-left: 0.25em solid var(--blockquote-border);
            background-color: rgba(139, 148, 158, 0.1);
            border-radius: 3px;
        }

        .badges {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 2em;
            color: #ffffff;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
        }

        .badge-python { background-color: #3776AB; }
        .badge-stdlib { background-color: var(--accent-green); }
        .badge-hermes { background-color: var(--accent-purple); }
        .badge-status { background-color: #2ea043; }

        pre {
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
            font-size: 85%;
            line-height: 1.45;
        }

        code {
            background-color: rgba(110, 118, 129, 0.4);
            border-radius: 6px;
            padding: 0.2em 0.4em;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
            font-size: 85%;
        }
        
        pre code {
            background-color: transparent;
            padding: 0;
        }

        table {
            border-spacing: 0;
            border-collapse: collapse;
            width: 100%;
            margin-top: 1em;
            margin-bottom: 1em;
        }

        table th, table td {
            padding: 8px 13px;
            border: 1px solid var(--border-color);
        }

        table th {
            font-weight: 600;
            background-color: var(--code-bg);
            text-align: left;
        }

        table tr:nth-child(2n) {
            background-color: rgba(110, 118, 129, 0.1);
        }

        .pipeline-diagram {
            background: var(--code-bg);
            padding: 20px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            font-family: monospace;
            white-space: pre;
            margin: 1.5rem 0;
            color: #7ee787;
        }

        .highlight { color: #ff7b72; font-weight: bold; }
        .footer { margin-top: 50px; text-align: center; font-size: 0.9em; color: #8b949e; border-top: 1px solid var(--border-color); padding-top: 20px;}
    </style>
</head>
<body>

    <h1>ANU Mind</h1>

    <div class="badges">
        <span class="badge badge-python">Python 3.11+</span>
        <span class="badge badge-stdlib">deps: stdlib only</span>
        <span class="badge badge-hermes">Hermes Skill</span>
        <span class="badge badge-status">Status: ACTIF PROD</span>
    </div>

    <blockquote>
        <strong>Moteur de raisonnement structuré multi-passes pour Hermes Agent.</strong><br>
        Déclenché via la commande <code>anu</code> ou le slash <code>/anu</code>, il implémente le pattern d'ingénierie "Reflexion" pour atténuer les hallucinations des LLMs. Le système applique un pipeline 4 passes : génération → audit asynchrone → remédiation (conditionnelle) → validation. L'intégration OS est assurée par le wrapper <code>anu-tg</code> avec exécution en <em>transient unit</em> systemd.
    </blockquote>

    <h2>1. Principes d'Architecture</h2>
    <p>ANU n’est pas un modèle fondationnel, mais un <strong>orchestrateur d'inférence structurée</strong>. Il contraint le LLM sous-jacent (Stepfun 3.7 flash via Hermes) à s'évaluer lui-même avant de délivrer son output. Cette approche casse le flux auto-régressif classique en injectant des étapes de validation déterministes.</p>

    <div class="pipeline-diagram">
 anu &lt;topic&gt;
        │
 [P1] ━━┿━━ Génération initiale (Injection du System Prompt par Archétype)
        │
 [P2] ━━┿━━ Audit Statique + Scoring Matriciel (5 dimensions, 0-10)
        │
 [P3] ━━┿━━ <span class="highlight">Correction ciblée</span> (Bifurcation si moyenne &lt; 7.0 OU dim &lt; 5)
        │
 [P4] ━━┿━━ Synthèse finale & Compilation Markdown → livrable p4.md
    </div>

    <h2>2. Structure du Dépôt (Single Source of Truth)</h2>
    <pre><code>anu/
├── tool.py                    ← Point d’entrée prod (lié vers ~/.local/bin/anu)
├── scripts/
│   ├── engine.py              ← Moteur 4-passes statique (zéro dépendance externe)
│   └── patch_auth.py          ← Utilitaire de remédiation Auth Telegram
├── install/
│   ├── anu-tg.sh              ← Wrapper Bash (Injection Env & Routage TG)
│   └── install.sh             ← Déploiement idempotent (ln -snf)
├── references/                ← Documentation d'ingénierie et de conception
│   ├── modes.md               ← Spécifications des 7 archétypes
│   ├── stepfun-nous-backend.md
│   ├── nous-model-naming.md
│   ├── provider-backend.md
│   └── ns-documentation.md
├── templates/
│   └── checkpoint_v1.json     ← Schéma contractuel d'état (State Machine)
├── tests/
│   ├── test_anu_tool.py
│   └── test_engine_integration.py
├── backups/                   ← Snapshots pré-déploiement (engine.py)
├── tool/
│   ├── anu_tool.py            ← Hook Hermes historique
│   └── tool_definition.json   ← Registration du Skill dans l'Event Loop Hermes
├── docs/
│   └── manuel_utilisation_fr.md
├── SKILL.md                   ← Metadata Hermes
└── README.md</code></pre>

    <h2>3. Déploiement & Intégration Système</h2>
    <p>L'installation s'appuie sur des liens symboliques pour garantir que le dépôt Git reste l'unique source de vérité. Le script d'installation garantit l'idempotence des chemins utilisateur.</p>
    
    <pre><code># Provisionnement et sécurisation de l'environnement CLI
bash install/install.sh

# Topologie post-déploiement attendue :
# ~/.local/bin/anu    -> <repo>/tool.py
# ~/.local/bin/anu-tg -> <repo>/install/anu-tg.sh</code></pre>

    <h2>4. Usage & Interface CLI</h2>
    <p>Le binaire est conçu pour fonctionner en mode synchrone (bloquant) ou asynchrone (détaché via systemd).</p>
    <pre><code>anu &lt;topic&gt;               # Cold start (détection automatique de l'archétype)
anu &lt;topic&gt; --mode N      # Forçage de l'archétype métier (1-7)
anu &lt;topic&gt; --detach      # Exécution asynchrone + Callback Telegram IPC
anu --resume &lt;run_id&gt;     # Reprise sur échec (réhydrate le contexte depuis Px.json)
anu --status              # Topologie des 20 derniers runs (Actifs/Échoués/Terminés)</code></pre>

    <h3>Exemples d'Invocation</h3>
    <pre><code>anu "audit SSH hardening" --mode 5
anu "refactor parser.py" --mode 2
anu "architecture NAS backup" --mode 1 --detach
anu --resume 20260719_132400</code></pre>

    <h2>5. Matrices des Archétypes (Modes)</h2>
    <p>Le routage heuristique sélectionne le <code>system_prompt</code> optimal si aucun flag <code>--mode</code> n'est explicitement fourni.</p>
    <table>
        <thead>
            <tr><th>Mode</th><th>Codename</th><th>Domaine de compétence</th><th>Triggers Heuristiques (Regex)</th></tr>
        </thead>
        <tbody>
            <tr><td>1</td><td>ARCHITECT</td><td>Architecture logicielle, topologie infra</td><td><code>architecture, design, schema, stack</code></td></tr>
            <tr><td>2</td><td><strong>CODER</strong></td><td>Génération de code, refactoring, debug</td><td><code>code, debug, script, refactor</code> <em>(Défaut)</em></td></tr>
            <tr><td>3</td><td>TEACHER</td><td>Vulgarisation technique, documentation</td><td><code>explique, tutoriel, documentation</code></td></tr>
            <tr><td>4</td><td>PROTOCOL</td><td>Workflows, standardisation, specs</td><td><code>procedure, spec, protocole, yaml</code></td></tr>
            <tr><td>5</td><td>AUDITOR</td><td>Hardening, analyse de risques, CVEs</td><td><code>audit, securite, risque</code></td></tr>
            <tr><td>6</td><td>WRITER</td><td>Rédaction formelle, rapports hiérarchiques</td><td><code>redige, article, rapport</code></td></tr>
            <tr><td>7</td><td>RESEARCHER</td><td>Benchmark, analyse comparative</td><td><code>recherche, compare, benchmark</code></td></tr>
        </tbody>
    </table>

    <h2>6. Moteur d'Audit P2 : Dimensions de Scoring</h2>
    <p>Si la moyenne globale chute sous <strong>7.0/10</strong> ou si une dimension critique (risques, factualité) obtient une note <strong>&lt; 5</strong>, le moteur bifurque sur P3 (Remédiation) avant de compiler P4. Les poids sont stricts et le LLM doit justifier chaque décimale.</p>
    <table>
        <thead>
            <tr><th>Dimension</th><th>Vecteur d'analyse</th><th>Seuil d'Alerte</th></tr>
        </thead>
        <tbody>
            <tr><td><code>factualite</code></td><td>Exactitude, absence d'hallucinations techniques</td><td>&lt; 5 (Critique)</td></tr>
            <tr><td><code>couverture</code></td><td>Exhaustivité de la réponse face au prompt initial</td><td>&lt; 5</td></tr>
            <tr><td><code>coherence</code></td><td>Linéarité logique, absence de contradictions internes</td><td>&lt; 5</td></tr>
            <tr><td><code>risques</code></td><td>Identification des impacts collatéraux (sécu/prod)</td><td>&lt; 5 (Critique)</td></tr>
            <tr><td><code>clarte</code></td><td>Lisibilité, formatage Markdown, scannabilité</td><td>&lt; 5</td></tr>
        </tbody>
    </table>

    <h2>7. Asynchronisme & Observabilité (Mode Detach)</h2>
    <p>L'utilisation de <code>--detach</code> isole le processus de la session shell courante via <code>systemd-run</code>.</p>
    <ul>
        <li><strong>Process Isolation :</strong> Création d'une <em>transient unit</em> (<code>systemd-run --user --unit=anu-run-&lt;run_id&gt;</code>). Rendu main la main au shell en &lt; 2s.</li>
        <li><strong>Environment Propagation :</strong> Les variables critiques (<code>TELEGRAM_CHAT_ID</code>, <code>DBUS_SESSION_BUS_ADDRESS</code>, <code>HERMES_PROFILE</code>) sont poussées en RAM dans le contexte de l'unité.</li>
        <li><strong>Callback Routing :</strong> Le livrable final (P4) est streamé via le broker Telegram. Les payloads massifs (&gt; 4096 octets) sont automatiquement fragmentés en chunks.</li>
    </ul>

    <h3>Structure des Artefacts de Run</h3>
    <pre><code>~/.hermes/profiles/&lt;profile&gt;/cron/output/anu/&lt;run_id&gt;/
├── p1.md / p1.json
├── p2.md / p2.json    ← Matrice de scoring
├── p3.md / p3.json    ← Instancié uniquement si P2 déclenche un trigger
├── p4.md / p4.json    ← Livrable consolidé
└── .manifest.json     ← Écriture atomique (.tmp + os.replace) pour intégrité d'état</code></pre>

    <h2>8. Posture de Sécurité & Résolution des Secrets</h2>
    <p>L'architecture ANU est conçue selon le principe du moindre privilège (Zero Trust local) :</p>
    <ul>
        <li><strong>Memory-Only Secrets :</strong> Les tokens ne sont jamais passés en arguments CLI (<code>argv</code>) pour éviter la fuite dans <code>ps aux</code> ou le <code>.bash_history</code>.</li>
        <li><strong>Log Masking :</strong> Le token Telegram est dynamiquement tronqué dans le logger (<code>abcd****...wxyz</code>).</li>
        <li><strong>Code Execution :</strong> Aucune fonction dynamique de type <code>eval()</code>, <code>exec()</code> ou <code>subprocess</code> direct depuis le LLM. L'agent est contraint à la génération de texte.</li>
    </ul>
    
    <p><strong>Hiérarchie de résolution des credentials :</strong></p>
    <ol>
        <li>Environnement dynamique enfant (<code>TELEGRAM_BOT_TOKEN</code>) injecté par wrapper.</li>
        <li>Profil courant (<code>~/.hermes/auth.json</code>).</li>
        <li>Configuration système (<code>config.yaml</code>).</li>
    </ol>

    <h2>9. Changelog Technique</h2>
    <h3>v0.9.1 — Juillet 2026</h3>
    <ul>
        <li><strong>[feat]</strong> Implémentation du déploiement idempotent des symlinks système via <code>install.sh</code> (<code>mkdir -p</code> + <code>ln -snf</code>).</li>
        <li><strong>[feat]</strong> Intégration du script de routage Telegram (<code>anu-tg.sh</code>) dans le contrôle de version.</li>
        <li><strong>[maint]</strong> Migration vers un modèle de Single Source of Truth intégral (zéro modification manuelle dans <code>~/.local/bin/</code>).</li>
    </ul>

    <h3>v0.9.0 — Juillet 2026</h3>
    <ul>
        <li>Validation du moteur 4-passes statique.</li>
        <li>Ajout des hooks <code>systemd-run</code> (mode <code>--detach</code>).</li>
        <li>Création de la machine d'état (<code>--status</code>, <code>--resume</code>).</li>
    </ul>

    <div class="footer">
        Mainteneur : <strong>Coresynq IT</strong> — g33ky<br>
        Implémentation architecturée par Hermes Agent (Stepfun 3.7 flash, profil dev) depuis Pytheas.<br>
        <em>Composant de l'écosystème Hermes — 🌿 2026</em>
    </div>

</body>
</html>
