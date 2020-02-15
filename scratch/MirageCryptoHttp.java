import java.security.KeyPair;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import org.apache.http.HttpRequest;
import org.apache.http.message.BasicHttpRequest;


public class MirageCrypto {
    private static int SALT_BYTES = 32;
    private static final byte[] KEY_INFO = "ENCRYPTION".getBytes(StandardCharsets.US_ASCII);

    public static void encrypt(String keyfile) throws CryptoUtilities.CryptoException, IOException {
        byte[] shared_key = Files.readAllBytes(Paths.get(keyfile));
        byte[] message = System.in.readAllBytes();
        System.out.write(CryptoUtilities.encrypt(message, shared_key));
    }

    public static void decrypt(String keyfile) throws CryptoUtilities.CryptoException, IOException {
        byte[] shared_key = Files.readAllBytes(Paths.get(keyfile));
        byte[] message = System.in.readAllBytes();
        System.out.write(CryptoUtilities.decrypt(message, shared_key));
    }

    public static void genkey(String name) throws CryptoUtilities.CryptoException, IOException {
        byte[] salt = CryptoUtilities.generateRandom(SALT_BYTES);
        KeyPair kp = CryptoUtilities.generateECDHKeyPair();
        byte[] publicKeyBytes = CryptoUtilities.convertECDHPublicKeyToBytes(kp.getPublic());
        FileOutputStream kpf = new FileOutputStream(name + ".key");
        ObjectOutputStream oos = new ObjectOutputStream(kpf);

        oos.writeObject(kp);
        oos.close();
        kpf.close();

        Files.write(Paths.get(name + ".pub"), publicKeyBytes);
        Files.write(Paths.get(name + ".salt"), salt);
    }

    public static void genshared(String me, String peer) throws CryptoUtilities.CryptoException, IOException, ClassNotFoundException {
        FileInputStream kpf = new FileInputStream(me + ".key");
        ObjectInputStream ois = new ObjectInputStream(kpf);
        KeyPair me_kp = (KeyPair) ois.readObject();
        ois.close();
        kpf.close();

        byte[] me_pkb = CryptoUtilities.convertECDHPublicKeyToBytes(me_kp.getPublic());
        byte[] me_salt = Files.readAllBytes(Paths.get(me + ".salt"));
        byte[] peer_pkb = Files.readAllBytes(Paths.get(peer + ".pub"));
        byte[] peer_salt = Files.readAllBytes(Paths.get(peer + ".salt"));

        byte[] keyMaterial = CryptoUtilities.generateECDHMasterKey(me_kp, peer_pkb);
        byte[] salt = CryptoUtilities.xor(me_salt, peer_salt);
        byte[] sharedKey = CryptoUtilities.generateHKDFBytes(keyMaterial, salt, KEY_INFO);

        Files.write(Paths.get(me + "_" + peer + ".skey"), sharedKey);
    }

    public static void sign(String skey) throws CryptoUtilities.CryptoException, IOException {
        byte[] shared_key = Files.readAllBytes(Paths.get(skey));
        HttpRequest request = new BasicHttpRequest("GET", "/media/0");
        byte[] testBody = "test".getBytes(StandardCharsets.UTF_8);
        ArrayList<byte[]> messages = new ArrayList<byte[]>();
        messages.add(request.getRequestLine().getMethod().getBytes(StandardCharsets.UTF_8));
        messages.add(request.getRequestLine().getUri().getBytes(StandardCharsets.UTF_8));
        messages.add(testBody);
        //System.out.println(request.getRequestLine().getMethod());
        //System.out.println(request.getRequestLine().getUri());

        byte[] hmac = CryptoUtilities.generateHMAC(shared_key, messages);
        //System.out.write(hmac);
        System.out.println(Base64.encodeToString(hmac, Base64.NO_WRAP | Base64.URL_SAFE));
        
    }

    public static void main(String[] args) {
        try {
            if (args.length == 0) {
                usage();
            } else if (args[0].equals("genkey")) {
                genkey(args[1]);
            } else if (args[0].equals("genshared")) {
                genshared(args[1], args[2]);
            } else if (args[0].equals("encrypt")) {
                encrypt(args[1]);
            } else if (args[0].equals("decrypt")) {
                decrypt(args[1]);
            } else if (args[0].equals("sign")) {
                sign(args[1]);
            } else {
                usage();
            }
        } catch (Exception e) {
              e.printStackTrace();
        }
    }

    public static void usage() {
        System.out.println("Usage:");
        System.out.println("java -cp . MirageCrypto genkey <name>");
        System.out.println("java -cp . MirageCrypto genshared <myname> <peername>");
        System.out.println("java -cp . MirageCrypto encrypt <shared_key>");
        System.out.println("java -cp . MirageCrypto decrypt <shared_key>");
    }

  public static String byteArrayToHex(byte[] a) {
   StringBuilder sb = new StringBuilder(a.length * 2);
   for(byte b: a)
      sb.append(String.format("%02x", b));
   return sb.toString();
  }
}
