"""Block to fix annotation of UD Indonesian-GSD."""
from udapi.core.block import Block
import logging
import re

class FixGSD(Block):

    def fix_upos_based_on_morphind(self, node):
        """
        Example from data: ("kesamaan"), the correct UPOS is NOUN, as
        suggested by MorphInd.
        Based on my observation so far, if there is a different UPOS between
        the original GSD and MorphInd, it's better to trust MorphInd
        I found so many incorrect UPOS in GSD, especially when NOUNs become
        VERBs and VERBs become NOUNs.
        I suggest adding Voice=Pass when the script decides ke-xxx-an as VERB.
        """
        if node.upos == 'VERB' and node.xpos == 'NSD' and re.match(r'^ke.+an$', node.form, re.IGNORECASE):
            node.upos = 'NOUN'
            if node.udeprel == 'acl':
                node.deprel = 'nmod'
            elif node.udeprel == 'advcl':
                node.deprel = 'obl'

    def fix_ordinal_numerals(self, node):
        """
        Ordinal numerals should be ADJ NumType=Ord in UD. They have many different
        UPOS tags in Indonesian GSD. This method harmonizes them.
        pertama = first
        kedua = second
        ketiga = third
        keempat = fourth
        kelima = fifth
        keenam = sixth
        ketujuh = seventh
        kedelapan = eighth
        kesembilan = ninth
        ke48 = 48th
        """
        # We could also check the XPOS, which is derived from MorphInd: re.match(r'^CO-', node.xpos)
        if re.match(r'^(pertama|kedua|ketiga|keempat|kelima|keenam|ketujuh|kedelapan|kesembilan|ke-?\d+)(nya)?$', node.form, re.IGNORECASE):
            node.upos = 'ADJ'
            node.feats['NumType'] = 'Ord'
            if re.match(r'^(det|nummod|nmod)$', node.udeprel):
                node.deprel = 'amod'
        # The following is not an ordinal numeral but I am too lazy to create a separate method for that.
        elif node.form.lower() == 'semua':
            # It means 'all'. Originally it was DET, PRON, or ADV.
            node.upos = 'DET'
            node.feats['PronType'] = 'Tot'
            if node.udeprel == 'nmod' or node.udeprel == 'advmod':
                node.deprel = 'det'

    def lemmatize_verb_from_morphind(self, node):
        # The MISC column contains the output of MorphInd for the current word.
        # The analysis has been interpreted wrongly for some verbs, so we need
        # to re-interpret it and extract the correct lemma.
        if node.upos == "VERB":
            morphind = node.misc["MorphInd"]
            # Remove the start and end tags from morphind.
            morphind = re.sub(r"^\^", "", morphind)
            morphind = re.sub(r"\$$", "", morphind)
            # Remove the final XPOS tag from morphind.
            morphind = re.sub(r"_VS[AP]$", "", morphind)
            # Split morphind to prefix, stem, and suffix.
            morphemes = re.split(r"\+", morphind)
            # Expected suffixes are -kan, -i, -an, or no suffix at all.
            # There is also the circumfix ke-...-an which seems to be nominalized adjective:
            # "sama" = "same, similar"; "kesamaan" = "similarity", lemma is "sama";
            # but I am not sure what is the reason that these are tagged VERB.
            if len(morphemes) > 1 and re.match(r"^(kan|i|an(_NSD)?)$", morphemes[-1]):
                del morphemes[-1]
            # Expected prefixes are meN-, di-, ber-, peN-, ke-, ter-, se-, or no prefix at all.
            # There can be two prefixes in a row, e.g., "ber+ke+", or "ter+peN+".
            while len(morphemes) > 1 and re.match(r"^(meN|di|ber|peN|ke|ter|se|per)$", morphemes[0]):
                del morphemes[0]
            # Check that we are left with just one morpheme.
            if len(morphemes) != 1:
                logging.warning("One morpheme expected, found %d %s, morphind = '%s', form = '%s', feats = '%s'" % (len(morphemes), morphemes, morphind, node.form, node.feats))
            else:
                lemma = morphemes[0]
                # Remove the stem POS category.
                lemma = re.sub(r"<[a-z]+>(_.*)?$", "", lemma)
                node.lemma = lemma

    def merge_reduplicated_plural(self, node):
        # Instead of compound:plur, merge the reduplicated plurals into a single token.
        if node.deprel == "compound:plur":
            root = node.root
            # We assume that the previous token is a hyphen and the token before it is the parent.
            first = node.parent
            if first.ord == node.ord-2 and first.form.lower() == node.form.lower():
                hyph = node.prev_node
                if hyph.is_descendant_of(first) and re.match(r"^(-|–|--)$", hyph.form):
                    # Neither the hyphen nor the current node should have children.
                    # If they do, re-attach the children to the first node.
                    for c in hyph.children:
                        c.parent = first
                    for c in node.children:
                        c.parent = first
                    # Merge the three nodes.
                    first.form = first.form + "-" + node.form
                    first.feats["Number"] = "Plur"
                    if node.no_space_after:
                        first.misc["SpaceAfter"] = "No"
                    else:
                        first.misc["SpaceAfter"] = ""
                    hyph.remove()
                    node.remove()
                    # We cannot be sure whether the original annotation correctly said that there are no spaces around the hyphen.
                    # If it did not, then we have a mismatch with the sentence text, which we must fix.
                    # The following will also fix cases where there was an n-dash ('–') instead of a hyphen ('-').
                    root.text = root.compute_text()

    def fix_plural_propn(self, node):
        """
        It is unlikely that a proper noun will have a plural form in Indonesian.
        All examples observed in GSD should actually be tagged as common nouns.
        """
        if node.upos == 'PROPN' and node.feats['Number'] == 'Plur':
            node.upos = 'NOUN'
            node.lemma = node.lemma.lower()
        if node.upos == 'PROPN':
            node.feats['Number'] = ''

    def process_node(self, node):
        self.fix_plural_propn(node)
        self.fix_upos_based_on_morphind(node)
        self.fix_ordinal_numerals(node)
        self.lemmatize_verb_from_morphind(node)
