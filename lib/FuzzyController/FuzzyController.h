#ifndef FUZZYCONTROLLER_H
#define FUZZYCONTROLLER_H

#include <string>

#include "FuzzyVariable.h"
#include "Utils.h"

/**
 * @brief Check given rule syntax in ruleCheck function. Set to 0 for
 * skipping syntax check.
**/
#define CHECK_RULE_SYNTAX 1

/**
 * @brief Class implementation of fuzzy controller using FuzzyVariable as
 * input and output. 
 * @details Provide set of rules using syntax 
 * "IF [A] IS [B] THEN [C] IS [D] " 
 * with A and C as variables, B and D as value of variable.
 * Has 3 step of process, Input -> Process -> Output, with multiple In->Out Mapping.
**/
class FuzzyController
{
	private:
		/**
		 * @brief Matrix used to sequence Process. Input-output and membership mapping
		 * for faster process.
		 * @details Matrix :
		 * | AIi AIm AOi AOm |
		 * | BIi BIm BOi BOm |
		 * | CIi CIm COi COm |
		 * with :
		 * A, B, C = Process index.
		 * Ii = Input array index.
		 * Im = Input membership array index.
		 * Oi = Output array index.
		 * Om = Output membership array index.
		**/
		int** process_matrix;
		FuzzyVariable* fuzzy_input;
		FuzzyVariable* fuzzy_output;
		int input_count;
		int output_count;
		std::string* rules_list;
		rules_t* rules;
		int rules_count;
		const int rules_syntax_length = 8;
		
		rules_t* ruleCheck(std::string);
		
	public:
		FuzzyController();
		~FuzzyController();
		void setInput(FuzzyVariable);
		void setOutput(FuzzyVariable);
		void setRules(std::string);
		void process();
		
		void updateProcessMatrix();
		
		std::string* getRules(){return rules_list;};
};

#endif