#! /usr/bin/env python
import csv
import json
import click

from drmlookup import build_algdrmlookup_with_numalgs

import numpy as np
from sklearn import linear_model
from scipy.stats import fisher_exact


GENE_CHOICES = ('PR', 'RT', 'IN')
SIGNIFICANCE_LEVEL = 0.01
MIN_TREATED_CASES = 3
MAX_NAIVE_PCNT = 0.005
MIN_FOLD_CHANGE = 2
ALGDRMLOOKUP = build_algdrmlookup_with_numalgs()


@click.command()
@click.option('-i', '--prevalence-file', type=click.File('r'),
              help='input prevalence source')
@click.option('-o', '--output-file', type=click.File('w'),
              help='output target TSV')
@click.option('--major-subtypes', multiple=True, type=str,
              default=('A', 'B', 'C', 'CRF01_AE', 'CRF02_AG', 'D', 'F', 'G'),
              show_default=True, help='stat for these subtypes')
@click.option('--no-subtype', is_flag=True, help='don\'t stat for subtypes')
@click.argument('gene', required=True,
                type=click.Choice(GENE_CHOICES))
def create_prevalence_table(
        prevalence_file, output_file,
        major_subtypes, no_subtype, gene):
    prevalence_data = json.load(prevalence_file)
    header = [
        'Position', 'AA',
        '# Naive (All)',
        '# Naive Cases (All)',
        'Naive Prev (All)',
        '# Treated (All)',
        '# Treated Cases (All)',
        'Treated Prev (All)'
    ]
    if no_subtype:
        major_subtypes = []
    else:
        for subtype in list(major_subtypes) + ['Others']:
            header.extend([
                'Naive Prev ({})'.format(subtype),
                '# Naive ({})'.format(subtype),
            ])
        header.extend([
            'Max Naive Total',
            'Max Naive Cases',
            'Max Naive Prev',
            'Max Naive Subtype',
        ])
    header.extend([
        'P Value',
        'Fold Change',
    ])
    writer = csv.DictWriter(
        output_file, header, extrasaction='ignore', delimiter='\t')
    writer.writeheader()
    rows = {}
    for item in prevalence_data:
        if item['gene'] != gene:
            continue
        pos = item['position']
        aa = item['aa']
        if (pos, aa) not in rows:
            rows[(pos, aa)] = {
                'Position': pos,
                'AA': aa,
                'Max Naive Prev': '0%',
                'Max Naive Total': 0,
                'Max Naive Subtype': '-',
            }
        row = rows[(pos, aa)]
        rx = item['rx_type']
        subtype = item['subtype']
        count = item['count']
        total = item['total']
        pcnt = item['percent']
        if subtype in ['All', 'Others'] + list(major_subtypes):
            if rx == 'naive':
                row['# Naive Cases ({})'.format(subtype)] = count
                row['Naive Prev ({})'.format(subtype)] = \
                    '{}%'.format(pcnt * 100)
                row['# Naive ({})'.format(subtype)] = total
            if rx == 'art':
                row['# Treated Cases ({})'.format(subtype)] = count
                row['Treated Prev ({})'.format(subtype)] = \
                    '{}%'.format(pcnt * 100)
                row['# Treated ({})'.format(subtype)] = total
        if subtype not in ('All', 'Others', 'Unknown') and rx == 'naive':
            if total < 200:
                # an arbitrary threshold
                continue
            if pcnt > float(row['Max Naive Prev'][:-1]) / 100:
                row['Max Naive Cases'] = count
                row['Max Naive Prev'] = '{}%'.format(pcnt * 100)
                row['Max Naive Total'] = total
                row['Max Naive Subtype'] = subtype

    for row in rows.values():
        pos = row['Position']
        aa = row['AA']
        naive_pos = row['# Naive Cases (All)']
        naive_neg = row['# Naive (All)'] - naive_pos
        treated_pos = row['# Treated Cases (All)']
        treated_neg = row['# Treated (All)'] - treated_pos
        obs = np.array([
            [naive_pos, naive_neg],
            [treated_pos, treated_neg]
        ])
        try:
            _, p = fisher_exact(obs)
            # _, p, _, _ = chi2_contingency(obs)
        except ValueError:
            p = 1.0
        fold_change = 1e2
        naive_pos_pcnt = float(row['Naive Prev (All)'][:-1]) / 100
        treated_pos_pcnt = float(row['Treated Prev (All)'][:-1]) / 100
        if naive_pos_pcnt > 0:
            fold_change = (treated_pos_pcnt / naive_pos_pcnt)
        row['P Value'] = p
        row['Fold Change'] = fold_change
        writer.writerow(row)


if __name__ == '__main__':
    create_prevalence_table()
