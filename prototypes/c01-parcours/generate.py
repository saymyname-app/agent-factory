"""Throwaway generator: renders the actual cockpit shell with synthetic fixtures."""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from cockpit.requests.model import OperatorRequest, A_FAIRE, QUAND_TU_VEUX
from cockpit.ui.home.page import render_requests_section
from cockpit.ui.base.page import render_home
from cockpit.ui.projects.page import render_projects_section
from cockpit.projects.model import Project, RoadmapStep, Chantier, LIVRAISON

HERE = Path(__file__).parent
STAMP = 1791723600  # 11 October 2026, 15:00 Paris; synthetic fixed clock.
requests = [
    OperatorRequest(id='demo-result', type='prototype_result', niveau=A_FAIRE,
        quoi='Le cockpit attend ton jugement', pourquoi='Un résultat est prêt à essayer, avec son dossier et ses limites.',
        que_faire=[], projet='Usine', depuis_quand=STAMP-1800, verifie_a=STAMP, reportable=False),
    OperatorRequest(id='demo-spec', type='prototype_spec', niveau=A_FAIRE,
        quoi='Une Spec attend ton approbation', pourquoi='Le périmètre de ce chantier reste à décider.',
        que_faire=[{'lettre':'a','option':'Continuer avec un agent','consequence':'Lis le périmètre avant de décider.'}],
        projet='Projet exemple', depuis_quand=STAMP-900, verifie_a=STAMP, reportable=False),
]
projects = [Project(project_id='demo-usine', display_name='Usine', promu_masque=True,
    roadmap_step=RoadmapStep('example','Améliorer le cockpit','in_progress'),
    chantiers=[Chantier('demo-result','Parcours du cockpit','demo-usine',LIVRAISON,'Résultat prêt pour ton jugement',etat='normal',promu_masque=True)]),
    Project(project_id='demo-other',display_name='Projet exemple',roadmap_unknown=True)]
extra = render_projects_section(projects) + '<section class="zone"><div class="zone-h"><h2>Santé de l’usine</h2></div><div class="zone-body"><p>Les sources synthétiques répondent.</p></div></section>'
page = render_home('Lectures vérifiées à 15:00 (Paris)', [], render_requests_section(requests,STAMP),
    status_html='En marche · 2 agents au travail', extra_sections_html=extra)
# No production scripts, polling, actions or external calls in this snapshot.
page = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', page)
page = re.sub(r'<link\b[^>]*>', '', page)
page = page.replace('</head>', '<style>'+HERE.joinpath('journey.css').read_text()+'</style></head>')
page = page.replace('<body id="cockpit-body">', '<body id="cockpit-body">'+HERE.joinpath('controls.html').read_text())
# A separate tab shows the application under test, not a step in the judging form.
import json
trial_requests = [
    OperatorRequest(id='trial-spec', type='prototype_spec', niveau=A_FAIRE,
        quoi='Valider le périmètre de recherche', pourquoi='Le projet Carnet ajoute une recherche par titre. Le périmètre proposé couvre les notes existantes.',
        que_faire=[], projet='Carnet', depuis_quand=STAMP-900, verifie_a=STAMP, reportable=False),
    OperatorRequest(id='trial-clarify', type='prototype_clarify', niveau=A_FAIRE,
        quoi='Préciser le comportement du tri', pourquoi='Le projet Carnet attend ton choix : ordre alphabétique ou dernière modification.',
        que_faire=[], projet='Carnet', depuis_quand=STAMP-300, verifie_a=STAMP, reportable=False),
]
trial_page = render_home('Version d’essai · données fictives', [], render_requests_section(trial_requests, STAMP),
    status_html='Cockpit à tester', extra_sections_html=render_projects_section([Project(project_id='trial-carnet', display_name='Carnet', roadmap_step=RoadmapStep('trial','Recherche et tri des notes','in_progress'))]))
trial_page = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', trial_page)
trial_body = re.search(r'<body[^>]*>([\s\S]*?)</body>', trial_page).group(1)
trial_body = '<div style="padding:12px 20px;background:var(--accent-soft)"><strong>Cockpit — version d’essai</strong> · exemples fictifs · reviens au premier onglet pour donner ton avis.</div>' + trial_body
trial_script = """
document.title='Cockpit — version d’essai';
document.body.innerHTML=TRIAL_BODY;
document.querySelectorAll('[data-action], form button').forEach(b=>b.disabled=true);
document.addEventListener('submit',e=>e.preventDefault());
const inbox=document.getElementById('inbox');
inbox.addEventListener('click',e=>{const row=e.target.closest('.li');if(row){e.preventDefault();document.querySelectorAll('.detail').forEach(d=>d.classList.toggle('on',d.id==='d-'+row.dataset.id));document.querySelectorAll('.li').forEach(r=>r.setAttribute('aria-current',r===row?'true':'false'));inbox.classList.add('sheet');}if(e.target.closest('.back')){e.preventDefault();inbox.classList.remove('sheet');}});
document.querySelectorAll('a').forEach(a=>{if(!a.classList.contains('li')&&!a.classList.contains('back')){a.removeAttribute('href');a.title='Exemple statique dans ce prototype';}});
""".replace('TRIAL_BODY',json.dumps(trial_body,ensure_ascii=False))
script = "if(new URLSearchParams(location.search).get('app')==='trial'){" + trial_script + "}else{const js=document.createElement('script');js.textContent=" + json.dumps(HERE.joinpath('journey.js').read_text(),ensure_ascii=False) + ";document.body.appendChild(js);}"
page = page.replace('</body>', '<script>'+script+'</script></body>')
HERE.joinpath('index.html').write_text(page)
print('Built actual render_home + render_requests_section + render_projects_section, synthetic data only.')
