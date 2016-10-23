import java.util.Random;

public class CaveBear extends GameObject{
	
	Random r = new Random();

	int maxHp = 55;
	
	public CaveBear(){
		dmg = 8;
		hp = 55;
		name = "CaveBear";
	}
}

