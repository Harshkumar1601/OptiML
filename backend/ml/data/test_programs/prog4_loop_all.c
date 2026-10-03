int main() {
    int sum = 0;
    int step = 2 * 4;
    int i = 0;
    while (i < 10) {
        int a = i + 1;
        int b = i + 1;
        sum = sum + a + b + step;
        i = i + 1;
    }
    return sum;
}