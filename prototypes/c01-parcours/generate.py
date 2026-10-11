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
page = page.replace('</body>', '<script>'+HERE.joinpath('journey.js').read_text()+'</script></body>')
HERE.joinpath('index.html').write_text(page)
print('Built actual render_home + render_requests_section + render_projects_section, synthetic data only.')
