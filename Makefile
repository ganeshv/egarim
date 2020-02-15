#CLASSES = $(patsubst %.java,%.class, $(wildcard *.java))

CLASSES = CryptoProvider.class CryptoUtilities.class DefaultCipherProvider.class MirageCrypto.class


%.class: %.java
	javac $<

all: $(CLASSES)

clean:
	rm -f *.class
