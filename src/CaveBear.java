import java.util.Random;

public class CaveBear extends GameObject{
	
	Random r = new Random();

	int maxHp;
	
	public CaveBear(){
		dmg = 8;
		hp = 55;
		name = "CaveBear";
		maxHp = 55;
	}
}

