#include <iostream>
#include <vector>

int main() {
    std::vector<int> v;
    for (int i = 0; i < 3; i++) { // bugprone-incorrect-roundings won't trigger, but style issues may
        v.push_back(i);
    }
    for (auto i : v) {
        std::cout << i << std::endl;
    }
    return 0;
}
