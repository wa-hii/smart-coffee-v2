#ifndef FUZZYVARIABLE_H
#define FUZZYVARIABLE_H

#include <string>

enum shape_t
{
	CLOSED,
	OPEN_HIGH,
	OPEN_LOW,
	CHOP_LOW,
	CHOP_HIGH
};

enum function_t
{
	TRIANGLE,
	SQUARE,
	TRAPEZOIDAL
};

class fuzzy_t
{
	private:
		std::string id;
		float value;
	public:
		fuzzy_t(){}
		fuzzy_t(std::string id_,float value_) : id(id_),value(value_){}
		std::string getId(){return id;}
		float getValue(){return value;}
		void setValue(float value_){value=value_;}
};

class rules_t
{
	private:
		std::string input_id;
		std::string input_value;
		std::string output_id;
		std::string output_value;
	public:
		rules_t(){}
		rules_t(std::string input_id_,std::string input_value_,std::string output_id_,std::string output_value_) : 
		input_id(input_id_),
		input_value(input_value_),
		output_id(output_id_),
		output_value(output_value_)
		{}
		rules_t(std::string rules);
		std::string getInputId() {return input_id;}
		std::string getInputValue() {return input_value;}
		std::string getOutputId() {return output_id;}
		std::string getOutputValue() {return output_value;}
};

class Triangle
{
	private:
		/**
		 * @brief Maximum membership value.
		**/
		float height;
		/**
		 * @brief X at minimum left.
		**/
		float l_side;
		/**
		 * @brief X at maximum right.
		**/
		float r_side;
		/**
		 * @brief X at midpoint.
		**/
		float mid;
		//not used maybe, i forgor
		float value;
		/**
		 * @brief Function shape.
		**/
		shape_t type;
		
	public:
		/**
		 * @brief Triangle-shaped membership.
		 * @param float, height/maximum membership value.
		 * @param float, minimum x value.
		 * @param float, x value at full membership.
		 * @param float, maximum x value.
		 * @param shape_t, function shape.
		**/
		Triangle(float,float,float,float,shape_t);
		/**
		 * @brief Get membership value at given x value
		**/
		float getPoint(float);
		//not used maybe, i forgor
		float getValue(){return value;}
		/**
		 * @brief Get middle point x.
		**/
		float getMid() {return mid;}
};

class Square
{
	private:
		/**
		 * @brief Maximum membership value.
		**/
		float height;
		/**
		 * @brief X at minimum left.
		**/
		float x_min;
		/**
		 * @brief X at maximum right.
		**/
		float x_max;
		/**
		 * @brief Function shape.
		**/
		shape_t type;
		
	public:
		Square(float,float,float,shape_t);
		/**
		 * @brief Get membership value at given x value
		**/
		float getPoint(float);
		/**
		 * @brief Get middle point x.
		**/
		float getMid() {return (x_max+x_min)/2;}
		/**
		 * @brief Get minimum x.
		**/
		float getMin() {return x_min;}
		/**
		 * @brief Get maximum x.
		**/
		float getMax() {return x_max;}
};

class Trapezoid
{
	private:
		/**
		 * @brief Middle side square function.
		**/
		Square *mid_side;
		/**
		 * @brief Left side triangle function.
		**/
		Triangle *left_side;
		/**
		 * @brief Right side triangle function.
		**/
		Triangle *right_side;
		/**
		 * @brief X at midpoint.
		**/
		float mid;
		/**
		 * @brief Function shape.
		**/
		shape_t type;
	
	public:
		/**
		 * @brief Trapezoid-shaped membership
		 * @param float, height/maximum membership value
		 * @param float, x value at minimum left.
		 * @param float, x value at full membership start point.
		 * @param float, x value at full membership stop point.
		 * @param float, x value at minimum right.
		 * @param shape_t, function shape.
		**/
		Trapezoid(float,float,float,float,float,shape_t);
		~Trapezoid();
		/**
		 * @brief Get membership value at given x value
		**/
		float getPoint(float);
		/**
		 * @brief Get middle point.
		**/
		float getMid() {return mid_side->getMid();}
};

/**
 * @brief Class implementation of fuzzy variable. Represent a fuzzy variable
 * with memberships.
 * @details Membership function type : Triangle, Square, Trapezoid
 * Membership function shape : CLOSED, OPEN_HIGH, OPEN_LOW, CHOP_HIGH,CHOP_LOW
**/
class FuzzyVariable
{
	private:
		/**
		 * @brief Variable identifier, name.
		**/
		std::string id;
		/**
		 * @brief Membership container.
		**/
		void** membership;
		/**
		 * @brief Membership function container.
		**/
		function_t* type;
		/**
		 * @brief Fuzzy value of each membership.
		**/
		fuzzy_t* fuzzies;
		/**
		 * @brief Membership counter.
		**/
		int counter;
	
	public:
		/**
		 * @brief Initialize fuzzy variable.
		 * @param std::string, Variable name. Default = ""
		**/
		FuzzyVariable(std::string="");
		~FuzzyVariable();
		/**
		 * @brief Setup membership of variable.
		 * @param std::string, Membership name/id.
		 * @param function_t, Membership function type.
		 * @param shape_t, Membership function shape.
		 * @param float[], Membership function parameters.
		**/
		void setMembership(std::string,function_t,shape_t,float*);
		/**
		 * @brief Check membership id.
		 * @param std::string, Membership id to check.
		 * @return int, Membership array index of given id. Return -1 if no match for id.
		**/
		int checkMembership(std::string);
		/**
		 * @brief Get current membership count.
		 * @return int, Membership count.
		**/
		int getMemberCount(){return counter;}
		/**
		 * @brief Get variable id.
		 * @return std::string, Variable id.
		**/
		std::string getId(){return id;}
		/**
		 * @brief Get fuzzy values.
		 * @return fuzzy_t[], Fuzzy value container.
		**/
		fuzzy_t* getFuzzies(){return fuzzies;}
		/**
		 * @brief Fuzzify given param. Fuzzy value of each membership will be modified.
		 * @param float, Value to fuzzify.
		**/
		void Fuzzyfication(float);
		/**
		 * @brief Defuzzify this variable, Get crisp value.
		 * @return float, Crisp value.
		**/
		float Defuzzyfication();
};

#endif