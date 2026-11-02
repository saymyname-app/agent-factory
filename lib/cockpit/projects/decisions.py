"""The open decisions of each chantier: the one reading the home, the page
of a project, the card of its chantier and its run share (R1, af-d6anqb;
Spec af-fgcw0d, user story 123, decision « État D01 commun aux vues » 2).

    decisions = chantier_decisions(chantiers, requests)
    decisions_line(decisions.get(chantier.id, 0))

``requests`` is the one « Ce qui t'attend » list the home counts
(:func:`cockpit.requests.assemble.assemble_requests`): each request names
the bead it is about. A request counts for the chantier that bead belongs
to -- the chantier's own bead (its convoy, its Spec), or one of the tickets
of its graph -- and for that chantier only. A request on no chantier's bead
counts for none.

Intent (constat of E, 22/10/2026): « l'accueil affiche « 6 décisions à
prendre », dont 4 demandes ouvertes sur des tickets du convoi af-strhoy
[…] mais la page projet agent-factory affiche « 0 Décisions attendues » ».
Mechanism (agent interpretation): the screens stop deriving « waiting »
each its own way (an état of the chantier, a timestamp on the ticket) and
count the same requests.

Pure: every input is a value the read model already holds.
"""


def chantier_decisions(chantiers, requests):
    """``{chantier id: how many open requests are about it}``, only for the
    chantiers some request is about. ``chantiers``:
    :class:`cockpit.projects.model.Chantier` rows; ``requests``: rows with
    an ``id``, the bead each is about."""
    owner = {}
    for chantier in chantiers or []:
        for bead_id in tuple(chantier.tickets or ()):
            owner.setdefault(bead_id, chantier.id)
    for chantier in chantiers or []:
        owner[chantier.id] = chantier.id
    counts = {}
    for request in requests or []:
        chantier_id = owner.get(getattr(request, "id", None))
        if chantier_id is not None:
            counts[chantier_id] = counts.get(chantier_id, 0) + 1
    return counts


def decisions_line(count):
    """What a screen says of ``count`` open decisions."""
    if not count:
        return "Aucune décision attendue"
    return "1 décision attendue" if count == 1 else "%d décisions attendues" % count
