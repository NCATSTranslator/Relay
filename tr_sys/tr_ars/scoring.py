import sympy
from sympy import symbols, expand, simplify, solve
import itertools
from operator import itemgetter
import numpy as np
import json


def main():
    print("here")
    f = open('/Users/williamsmard/Software/trashcan/mergeResults.json')

    # returns JSON object as
    # a dictionary
    data = json.load(f)

    compute_from_results(data)

def compute_from_results(results):
    sugeno_scores=[]
    weighted_means=[]
    for result in results:
        novelty=0
        confidence=0
        clinical_evidence=0
        score_blank_factor=0
        if 'ordering_components' in result.keys():
            if 'novelty' in result['ordering_components'].keys():
                novelty = result['ordering_components']['novelty']
            if 'confidence' in result['ordering_components'].keys():
                confidence = result['ordering_components']['confidence']
            if 'clinical_evidence' in result['ordering_components'].keys():
                clinical_evidence = result['ordering_components']['clinical_evidence']
        sugeno_score=compute_sugeno(confidence,novelty,clinical_evidence,score_blank_factor)[2]
        weighted_mean=compute_weighted_mean(confidence,novelty,clinical_evidence,score_blank_factor)

        sugeno_scores.append(sugeno_score)
        weighted_means.append(weighted_mean)
        result['sugeno']=sugeno_score
        result['weighted_mean']=weighted_mean

    final_ranks = compute_sugeno_weighted_mean_rank(sugeno_scores,weighted_means)[2]
    for i, rank in enumerate(final_ranks):
        #casting to int because some come through as pandas int64
        results[i]["rank"]=int(rank)
    results = sorted(results, key=lambda d: d['rank'])
    return results

'''
THIS FUNCTION PRODUCES THE WEIGHT SETS USED IN THE COMPUTATION OF THE SUGENO INTEGRAL
'''
def weight_sets(lambda_val, weight_confidence, weight_novelty, weight_clinical, weight_blank_factor, n=2):
    list_x = ['confidence', 'novelty', 'clinical', 'blank_factor']
    dict_t = {}
    for k in range(2, n+1):
        list_perm = list(itertools.permutations(list_x, r=k))
        for i in list_perm:
            t = "weight"
            t_l = "weight"
            t_f = "weight"
            for idj, j in enumerate(i):
                t = t + "_" + j
                if idj < k-1:
                    t_l = t_l + "_" + j
                if idj == k-1:
                    t_f = t_f + "_" + j
            # print(t, t_l, t_f)
            locals()[t] = locals()[t_l] + locals()[t_f] + (lambda_val * (locals()[t_l] * locals()[t_f]))
            dict_t[t] = round(float(locals()[t]), 2)
            # print(f"{t}:{locals()[t]}")
    dict_t["weight_confidence"] = weight_confidence
    dict_t["weight_novelty"] = weight_novelty
    dict_t["weight_clinical"] = weight_clinical
    dict_t["weight_blank_factor"] = weight_blank_factor
    return dict_t

'''
THIS FUNCTION COMPUTES THE SUGENO INTEGRAL FOR 4 WEIGHTS CONTRIBUTING TO EACH OF THE FACTORS AND 4 SCORES FOR A RESULT
'''
def compute_sugeno(score_confidence, score_novelty, score_clinical, score_blank_factor, weight_confidence=1.0, weight_novelty=0.1, weight_clinical=1.0, weight_blank_factor=0.0):
    x = symbols('lambda')
    polynomial = expand(((1+weight_confidence*x)*(1+weight_novelty*x)*(1+weight_clinical*x)*(1+weight_blank_factor*x))-(1+x))
    simplified_polynomial = simplify(polynomial)
    solutions = solve(simplified_polynomial, x)
    for i in solutions:
        if type(i)== sympy.core.add.Add:
            i = i.as_real_imag()[0]
        if i >= -1 and i!=0:
            lambda_val = i
    w_sets = weight_sets(lambda_val, weight_confidence, weight_novelty, weight_clinical, weight_blank_factor, n=4)

    score_all = [['confidence', score_confidence], ['novelty',score_novelty], ['clinical', score_clinical], ['blank_factor', score_blank_factor]]
    score_sorted = sorted(score_all, key=itemgetter(1), reverse=True)
    w_sorted = {}
    A= "weight"
    for idi, i in enumerate(score_sorted):
        A=A+"_"+i[0]
        w_sorted[A] = w_sets[A]
    keys = list(w_sorted.keys())
    sugeno = max(min(score_sorted[0][1],w_sorted[keys[0]]), min(score_sorted[1][1],w_sorted[keys[1]]), min(score_sorted[2][1], w_sorted[keys[2]]), min(score_sorted[3][1], w_sorted[keys[3]]))
    return score_sorted, w_sorted, sugeno

'''
THIS FUNCTION COMPUTES THE WEIGHTED MEAN FOR 4 WEIGHTS CONTRIBUTING TO EACH OF THE FACTORS AND 4 SCORES FOR A RESULT
'''
def compute_weighted_mean(score_confidence, score_novelty, score_clinical, score_blank_factor, weight_confidence=1.0, weight_novelty=0.1, weight_clinical=1.0, weight_blank_factor=0.0):
    weighted_mean = (score_confidence*weight_confidence + score_novelty*weight_novelty + score_clinical*weight_clinical + score_blank_factor*weight_blank_factor)/(weight_confidence+weight_novelty+ weight_clinical+weight_blank_factor)
    return weighted_mean

'''
THIS FUNCTION PRODUCES THE RANKING ORDER BASED SUGENO INTEGRAL, WEIGHTED MEAN AND SUGENO + WEIGHTED MEAN GIVEN A SET OF SUGENO AND WEIGHTED MEAN SCORES
'''
def compute_sugeno_weighted_mean_rank(sugeno_scores, weighted_mean_scores):
    sugeno_sorted = sorted(sugeno_scores, reverse=True)
    weighted_mean_sorted = sorted(weighted_mean_scores, reverse=True)
    sugeno_rank, weighted_mean_rank = [], []
    for item in sugeno_scores:
        sugeno_rank.append(sugeno_sorted.index(item) + 1)
    for item in weighted_mean_scores:
        weighted_mean_rank.append(weighted_mean_sorted.index(item) + 1)
    duplicates = {}
    sugeno_weighted_mean_rank = sugeno_rank.copy()
    for index, value in enumerate(sugeno_rank):
        if value in duplicates:
            duplicates[value].append(index)
        else:
            duplicates[value] = [index]
    duplicate_indices = {value: indices for value, indices in duplicates.items() if len(indices)>1}
    if len(duplicate_indices) != 0:
        for i in duplicate_indices.keys():
            weight_order = np.array(weighted_mean_rank)[duplicate_indices[i]]
            weight_order_copy = weight_order.copy()
            for idk, k in enumerate(sorted(weight_order)):
                weight_order_copy[list(weight_order).index(k)] = idk
            for idj, j in enumerate(duplicate_indices[i]):
                sugeno_weighted_mean_rank[j] = i + weight_order_copy[idj]
    return sugeno_rank, weighted_mean_rank, sugeno_weighted_mean_rank

if __name__ == "__main__":
    main()