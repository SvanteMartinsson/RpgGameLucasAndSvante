import java.util.Random;

public class GiantRat extends GameObject{

	
	Random r = new Random();
	
	public GiantRat(){
		dmg = 10;
		hp = 20;
		dodgeChance = r.nextInt(4) + 1;
		name = "Giant Rat";
		
	}
	
	public void attack() {
		
		
	}

}
