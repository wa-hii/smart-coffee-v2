#ifndef DYNAMIC_VARIABLE_H
#define DYNAMIC_VARIABLE_H

namespace dynvar{
    template <class T>
    class Container
    {
        private:
            T* cptr;
            int size;

        public:
            explicit Container(){}
            explicit Container(int size_) 
            {
                cptr = new T[size_];
                size = size_;
            }

            ~Container()
            {
                delete [] cptr;
            }

            void resize(int size_)
            {
                T* temp_cptr = cptr;
                cptr = new T[size_];
                for(int i = 0; i<size;i++)
                {
                    cptr[i] = temp_cptr[i];
                }
                size = size_;
                delete [] temp_cptr;
            }

            T& at(int idx){return cptr[idx];}
            T& operator*(){return *cptr;}

            int getSize() {return size;}
    };
}

#endif