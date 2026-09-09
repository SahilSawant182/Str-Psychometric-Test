# Skill verification prompts

`QUESTION_COUNT = 5` and `PASS_SCORE = 60` are fixed product rules. Keep prompts compact: skill and level are the variables sent when a quiz is generated.

## Quiz prompt

```text
Create exactly {question_count} fair questions that verify practical {skill} knowledge for a {level} learner. {mix_instruction} Match difficulty to this level. Cover distinct essentials. Keep all questions, options, and rubrics extremely concise and brief to minimize generation time. For mcq, ensure all 4 options in 'o' are completely distinct and mutually exclusive with no duplicates. Rubrics must be a single, short sentence of under 10 words. Return JSON only: {"questions":[{"type":"mcq|short_answer|long_answer|problem_solving","q":"...","o":["...","...","...","..."],"a":"A","rubric":"what a correct written answer must include","d":"easy|medium|hard"}]}. For mcq, include o and a where a is A-D. For non-mcq, set o to [] and a to "" and include a concise rubric. Keep every JSON string on one line with no raw line breaks or tab characters. No markdown or extra keys.
```

## Evaluation prompt

```text
You are a fair technical grader. For each item, write a brief comment analysing if the student_answer satisfies the rubric, then assign a score. RULES: 1. If student_answer clearly contains the correct concept or syntax described in the rubric, you MUST score it 80-100. 2. Do not penalize for extra information or different phrasing as long as the core requirement is met. 3. If student_answer is completely missing the required concept or contains fundamentally wrong syntax, score it 0-40. 4. For partial answers, score 40-60. Input: {input_data}. Return JSON only: {{"evaluations":[{{"index":number,"comment":"one sentence analysing the answer against the rubric","score":0-100}}]}}. Keep every JSON string on one line. No markdown or extra keys.
```

## Result prompt

```text
Return JSON only for this {skill} quiz. Score {score}% ({correct}/{total}); passed={passed}. Correct topics: {correct_topics}. Missed topics: {missed_topics}. Strengths must only be drawn from correct topics, and gaps must only be drawn from missed topics (if there are no missed topics, gaps must be an empty list []). Schema: {"summary":"one concise sentence","strengths":["up to 2 concise items"],"gaps":["up to 2 concise items"],"next_step":"one concrete action","status":"verified|not_verified"}. status must match passed. No markdown or extra keys.
```

The UI owns the score and verification decision. The model only supplies the consistently structured learning feedback.
