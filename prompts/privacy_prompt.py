curate_data_prompt = f"""
Your task is to generalize the given 'disclosure span' in the sentence.
Provide three diverse generalized spans that convey similar meaning but remove any overly specific or sensitive information.

Example 1:
Sentence:"Should I submit a 1470 SAT score to Carnegie Mellon and Dukes?"
Disclosure Span to Revise:"1470 SAT score"
Rationale:The original disclosure span explicitly states a specific SAT score, which may be sensitive information for some individuals.
To retain the context that the score is competitively high while removing the exact number, we can use generalized terms.
Generalized Spans:{{"span 1":"a high 1400 - range SAT score ","span 2":"an SAT score in the upper 1400 s","span 3":"an SAT score above 1450"}}

Example 2:
Sentence:"My Top Spotify Artists of 2022 were Charli XCX, Taylor Swift, Carly Rae Jepsen, Snow Strippers, and Danny L Harle."
Disclosure Span to Revise:"Top Spotify Artists of 2022 were Charli XCX, Taylor Swift, Carly Rae Jepsen, Snow Strippers, and Danny L Harle."
Generalized Spans:{{"span 1":"favorite artists of 2022 included a mix of pop and electronic musicians","span 2":"top artists from 2022 covered a range of styles","span 3":"favorite artists last year were from various genres"}}

Example 3:
Sentence:"I just turned 32 last month and have been really reflecting on my relationships with people from my relationship with my siblings to coworkers."
Disclosure Span to Revise:"just turned 32 last month"
Generalized Spans:{{"span 1":"recently entered my early 30s","span 2":"turned into my early thirties not long ago","span 3":"just started my third decade a little while back"}}

Offer three diverse generalized alternatives in a JSON format like this : {{"span 1":"xxx","span 2":"xxx","span 3":"xxx"}}.

Criteria:
* Only the disclosure span should be generalized; the rest of the sentence should remain intact.
* Generalized spans should be diverse but should all retain the essence of the original span.
* Make sure the generalized span fits seamlessly into the original sentence, maintaining proper syntax and grammar.
"""

message_prompt="""
# Sentence Safety Checker
Your task is to sanitize given sentence if it conveys overly specific or sensitive personal information.

## Goal
Your output has two goals:
1. **Identify whether the given sentence has any personally identifiable information disclosures**
2. **Substitute any personally identifiable information disclosures in the sentence with less personal equivalents.**

## Self Disclosure
There are 17 specific categories to consider:
* Age : "I am a 23-year-old".
* Gender : "I' m just a girl".
* Age_Gender : only when age and gender are combined in a *single* word, such as "20 F" or "32 M".
* Sexual_Orientation : "I' m a straight man".
* Race_Nationality : mentions of the user's nationality / race / ethnicity.
* Wife_GF : disclosures indicating the author has a wife, girlfriend, or fiancee, such as "My gf".
* Husband_BF : disclosures indicating the author has a husband, boyfriend, or fiance, such as "My bf".
* Relationship_Status : only includes mentions of marital status, being in a romantic relationship, or being single. For example, "my partner".
* Family : mentions of specific family members, as well as disclosures that related to themselves, such as "My child is 3 year old".
* Health : includes a wide range of health - related information , from discussing specific diseases or conditions to mentioning medications, medical tests, or treatments.
* Mental_Health : includes a broad range of emotional states and feelings , not necessarily limited to specific mental health diagnoses. Examples include feelings of sadness, anxiety, stress, or comments about struggling with emotional well - being in general.
* Location : captures specific geographical details disclosed by the author. It includes precise locations such as addresses, cities, countries, or distinctive landmarks, so vague spans like "this place" should not be categorized.
* Appearance : "I am 6 '2".
* Pet : "I have two musk turtles".
* Occupation : "I 'm a motorcycle tourer (by profession)", student should be categorized as Education.
* Education : "I got accepted to UCLA"
* Finance : any financial situations, not necessarily exact amounts.

## Examples
"Im 16F I think I want to be a bi M" -> "I'm a teenage girl and I'm exploring my sexual identity"
"Should I submit a 1470 SAT score to Carnegie Mellon and Duke?" -> "...an SAT score in the upper 1400s..."
"My Top Spotify Artists of 2022 were Charli XCX, Taylor Swift, Carly Rae Jepsen, Snow Strippers and Danny L Harle." -> "...favorite artists of 2022 included a mix of pop and electronic musicians."
"I just turned 32 last month and have been really reflecting on my relationships with people from my relationship with my siblings to coworkers." -> "...recently entered early 30s..."

## Output
- First identify whether the message has any disclosure spans.
- If it has disclosure spans, generalize spans that convey similar meaning but remove any overly specific or sensitive information.
- Only the disclosure span should be generalized; the rest of the sentence should remain intact.

Output **only JSON** in this format:
{
  "has_disclosure": "<true or false>",
  "spans":"<["span 1", "span 2", ...] or []>",
  "message": "<sanitized message or "">"
}
"""