# Skill verification prompts

`QUESTION_COUNT = 5` and `PASS_SCORE = 60` are fixed product rules. Keep prompts compact: skill and level are the variables sent when a quiz is generated.

## Quiz prompt

```text
Create exactly {question_count} fair questions that verify practical {skill} knowledge for a {level} learner. {mix_instruction} Match difficulty to this level. Cover distinct essentials. Keep all questions, options, and rubrics extremely concise and brief to minimize generation time. For mcq, ensure all 4 options in 'o' are completely distinct and mutually exclusive with no duplicates. Rubrics must be a single, short sentence of under 10 words. Return JSON only: {"questions":[{"type":"mcq|short_answer|long_answer|problem_solving","q":"...","o":["...","...","...","..."],"a":"A","rubric":"what a correct written answer must include","d":"easy|medium|hard"}]}. For mcq, include o and a where a is A-D. For non-mcq, set o to [] and a to "" and include a concise rubric. Keep every JSON string on one line with no raw line breaks or tab characters. No markdown or extra keys.
```

## Evaluation prompt

```text
You are a strict and highly rigorous technical grader. Evaluate these {skill} {level} answers. CRITICAL RULES: 1. You MUST strictly evaluate ONLY the text provided in 'student_answer'. DO NOT hallucinate, infer, or assume the student meant something they did not explicitly type. 2. If the 'student_answer' is missing required concepts, correct syntax, or key details described in the rubric, you MUST score it low (0 to 40). 3. If the question asks for code or specific syntax, the syntax MUST be correct and complete. Incorrect or incomplete syntax must result in a low score. 4. Do not give credit for vague attempts or partial effort that misses the core requirement. Assess the overall accuracy as a percentage (0-100). If the accuracy is less than {pass_score} percent, it is incorrect. Input: {input_data}. Return JSON only matching schema: {"evaluations":[{"index":number,"score":0-100,"is_correct":true|false,"comment":"one concise reason based ONLY on the exact student_answer provided"}]}. Mark is_correct true only when score is at least {pass_score}. Keep every JSON string on one line. No markdown or extra keys.
```

## Result prompt

```text
Return JSON only for this {skill} quiz. Score {score}% ({correct}/{total}); passed={passed}. Correct topics: {correct_topics}. Missed topics: {missed_topics}. Strengths must only be drawn from correct topics, and gaps must only be drawn from missed topics (if there are no missed topics, gaps must be an empty list []). Schema: {"summary":"one concise sentence","strengths":["up to 2 concise items"],"gaps":["up to 2 concise items"],"next_step":"one concrete action","status":"verified|not_verified"}. status must match passed. No markdown or extra keys.
```

The UI owns the score and verification decision. The model only supplies the consistently structured learning feedback.
